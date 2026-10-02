"""
Implementación de LyricsProvider conectada a la API pública de LRCLIB (https://lrclib.net)
con normalizador de títulos y caché local persistente en SQLite.
"""

import os
import re
import time
import sqlite3
from typing import Optional, Dict, Any
import requests

from contextlib import contextmanager

from .lyrics_models import LyricsResult, LyricsStatus
from .lyrics_provider_base import LyricsProvider
from .lrc_parser import parse_lrc

LRCLIB_GET_URL = "https://lrclib.net/api/get"
LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"

# Limpieza de coletillas comunes que arruinan la búsqueda exacta
TITLE_CLEANUP_REGEX = re.compile(
    r"\s*[-–]\s*(Remastered|Remaster|Live|Mono|Stereo|Deluxe|Radio Edit|Bonus Track).*$|\s*\((Remastered|Remaster|Live|feat\..*|ft\..*|Deluxe.*|Version.*)\)|\s*\[(.*)\]",
    re.IGNORECASE,
)


def normalize_title(title: str) -> str:
    """Limpia sufijos de remasterización, directos y colaboraciones en el título."""
    cleaned = TITLE_CLEANUP_REGEX.sub("", title).strip()
    return cleaned if cleaned else title


class LRCLIBLyricsProvider(LyricsProvider):
    """
    Proveedor de letras basado en LRCLIB con caché local SQLite.
    """

    def __init__(self, db_path: Optional[str] = None, timeout: float = 6.0):
        self.timeout = timeout
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "lyrics_cache.db")
        else:
            self.db_path = db_path

        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Inicializa la tabla de caché SQLite si no existe."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lyrics_cache (
                    cache_key TEXT PRIMARY KEY,
                    artist TEXT NOT NULL,
                    title TEXT NOT NULL,
                    album TEXT,
                    duration_ms INTEGER,
                    status TEXT NOT NULL,
                    synced_lyrics TEXT,
                    plain_lyrics TEXT,
                    cached_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def _make_cache_key(self, artist: str, title: str) -> str:
        clean_art = artist.lower().strip()
        clean_tit = normalize_title(title).lower().strip()
        return f"{clean_art}___{clean_tit}"

    def _get_from_cache(self, cache_key: str) -> Optional[LyricsResult]:
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM lyrics_cache WHERE cache_key = ?", (cache_key,)
                )
                row = cur.fetchone()
                if row:
                    status = LyricsStatus(row["status"])
                    synced_raw = row["synced_lyrics"]
                    lines = parse_lrc(synced_raw) if synced_raw else []
                    return LyricsResult(
                        status=status,
                        lines=lines,
                        plain_text=row["plain_lyrics"],
                        source="CACHE_SQLITE",
                        is_cached=True,
                    )
        except Exception as e:
            print(f"[LRCLIBProvider] Error leyendo caché SQLite: {e}")
        return None

    def _save_to_cache(
        self,
        cache_key: str,
        artist: str,
        title: str,
        album: Optional[str],
        duration_ms: Optional[int],
        status: LyricsStatus,
        synced_lyrics: Optional[str],
        plain_lyrics: Optional[str],
    ):
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO lyrics_cache 
                    (cache_key, artist, title, album, duration_ms, status, synced_lyrics, plain_lyrics, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        artist,
                        title,
                        album,
                        duration_ms,
                        status.value,
                        synced_lyrics,
                        plain_lyrics,
                        time.time(),
                    ),
                )
                conn.commit()
        except Exception as e:
            print(f"[LRCLIBProvider] Error guardando en caché SQLite: {e}")

    def get_lyrics(
        self,
        artist: str,
        title: str,
        album: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> LyricsResult:
        cache_key = self._make_cache_key(artist, title)

        # 1. Comprobar caché local
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result

        # 2. Consultar API de LRCLIB
        norm_title = normalize_title(title)
        headers = {"User-Agent": "AlexaLyricsTV/1.0 (https://github.com/alexa-lyrics-tv)"}

        # Intento A: Endpoint /api/get (búsqueda exacta)
        params: Dict[str, Any] = {
            "artist_name": artist,
            "track_name": norm_title,
        }
        if album:
            params["album_name"] = album
        if duration_ms:
            params["duration"] = int(duration_ms / 1000)

        data = None
        try:
            resp = requests.get(
                LRCLIB_GET_URL, params=params, headers=headers, timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
            elif resp.status_code == 404:
                # Si falla con álbum/duración exactos, probar búsqueda general
                search_resp = requests.get(
                    LRCLIB_SEARCH_URL,
                    params={"artist_name": artist, "track_name": norm_title},
                    headers=headers,
                    timeout=self.timeout,
                )
                if search_resp.status_code == 200:
                    items = search_resp.json()
                    if isinstance(items, list) and len(items) > 0:
                        data = items[0]  # Primer resultado relevante
            elif resp.status_code == 429:
                return LyricsResult(
                    status=LyricsStatus.ERROR,
                    error_message="LRCLIB Rate Limit (HTTP 429)",
                    source="LRCLIB_API",
                )
            else:
                return LyricsResult(
                    status=LyricsStatus.ERROR,
                    error_message=f"LRCLIB HTTP {resp.status_code}",
                    source="LRCLIB_API",
                )
        except requests.exceptions.Timeout:
            return LyricsResult(
                status=LyricsStatus.ERROR,
                error_message="LRCLIB Timeout",
                source="LRCLIB_API",
            )
        except requests.exceptions.RequestException as e:
            return LyricsResult(
                status=LyricsStatus.ERROR,
                error_message=f"LRCLIB Error de conexión: {str(e)}",
                source="LRCLIB_API",
            )

        # 3. Procesar datos obtenidos
        if not data:
            # Canción no encontrada en LRCLIB
            self._save_to_cache(
                cache_key=cache_key,
                artist=artist,
                title=title,
                album=album,
                duration_ms=duration_ms,
                status=LyricsStatus.NO_LYRICS,
                synced_lyrics=None,
                plain_lyrics=None,
            )
            return LyricsResult(status=LyricsStatus.NO_LYRICS, source="LRCLIB_API")

        synced_lyrics = data.get("syncedLyrics")
        plain_lyrics = data.get("plainLyrics")

        # Prioridad 1: syncedLyrics
        if synced_lyrics and synced_lyrics.strip():
            lines = parse_lrc(synced_lyrics)
            if lines:
                self._save_to_cache(
                    cache_key=cache_key,
                    artist=artist,
                    title=title,
                    album=album,
                    duration_ms=duration_ms,
                    status=LyricsStatus.SYNCED,
                    synced_lyrics=synced_lyrics,
                    plain_lyrics=plain_lyrics,
                )
                return LyricsResult(
                    status=LyricsStatus.SYNCED,
                    lines=lines,
                    plain_text=plain_lyrics,
                    source="LRCLIB_API",
                )

        # Prioridad 2: plainLyrics (no sincronizada)
        if plain_lyrics and plain_lyrics.strip():
            self._save_to_cache(
                cache_key=cache_key,
                artist=artist,
                title=title,
                album=album,
                duration_ms=duration_ms,
                status=LyricsStatus.UNSYNCED,
                synced_lyrics=None,
                plain_lyrics=plain_lyrics,
            )
            return LyricsResult(
                status=LyricsStatus.UNSYNCED,
                lines=[],
                plain_text=plain_lyrics,
                source="LRCLIB_API",
            )

        # Prioridad 3: Sin letras
        self._save_to_cache(
            cache_key=cache_key,
            artist=artist,
            title=title,
            album=album,
            duration_ms=duration_ms,
            status=LyricsStatus.NO_LYRICS,
            synced_lyrics=None,
            plain_lyrics=None,
        )
        return LyricsResult(status=LyricsStatus.NO_LYRICS, source="LRCLIB_API")
