"""
Adaptador de reproducción para Spotify Web API.
Implementa el flujo OAuth 2.0 (Authorization Code), renovación de tokens
y normalización de datos hacia PlaybackState.
"""

import os
import json
import time
import base64
import urllib.parse
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv

from .models import PlaybackState
from .provider_base import PlaybackProvider

load_dotenv()

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_PLAYER_URL = "https://api.spotify.com/v1/me/player"

# Scopes estrictamente mínimos para lectura de estado
SCOPES = ["user-read-playback-state", "user-read-currently-playing"]


class SpotifyPlaybackProvider(PlaybackProvider):
    """
    Proveedor de reproducción conectado a la Spotify Web API.
    Diseñado para observar la reproducción activa en altavoces Amazon Echo vía Spotify Connect.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        tokens_file: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv(
            "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
        )
        self.tokens_file = tokens_file or os.getenv(
            "SPOTIFY_TOKENS_FILE",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tokens.json"),
        )
        self.tokens: Dict[str, Any] = self._load_tokens()

    def _load_tokens(self) -> Dict[str, Any]:
        """Carga tokens persistidos desde el archivo local de tokens."""
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[SpotifyProvider] Error al leer tokens de {self.tokens_file}: {e}")
        return {}

    def _save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Guarda tokens en almacenamiento seguro local."""
        self.tokens = tokens
        os.makedirs(os.path.dirname(os.path.abspath(self.tokens_file)), exist_ok=True)
        with open(self.tokens_file, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)

    def is_authenticated(self) -> bool:
        """Verifica si existe un refresh token o access token válido."""
        return bool(self.tokens.get("refresh_token") or self.tokens.get("access_token"))

    def get_authorization_url(self, state: str = "lyrics_tv_auth") -> str:
        """
        Genera la URL oficial de Spotify para autorizar la cuenta de Camila.
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(SCOPES),
            "state": state,
            "show_dialog": "true",  # Permite verificar explícitamente la cuenta que inicia sesión
        }
        return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Intercambia el código de autorización por access_token y refresh_token.
        """
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("utf-8")

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        resp = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data, timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Error al intercambiar código por tokens (HTTP {resp.status_code}): {resp.text}"
            )

        payload = resp.json()
        payload["expires_at"] = time.time() + payload.get("expires_in", 3600) - 60
        self._save_tokens(payload)
        return payload

    def refresh_access_token(self) -> bool:
        """
        Renueva el access token usando el refresh_token almacenado.
        """
        refresh_token = self.tokens.get("refresh_token")
        if not refresh_token:
            print("[SpotifyProvider] No hay refresh_token disponible para renovar sesión.")
            return False

        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("utf-8")

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            resp = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data, timeout=10)
            if resp.status_code == 200:
                new_tokens = resp.json()
                self.tokens["access_token"] = new_tokens["access_token"]
                self.tokens["expires_at"] = (
                    time.time() + new_tokens.get("expires_in", 3600) - 60
                )
                if "refresh_token" in new_tokens:
                    self.tokens["refresh_token"] = new_tokens["refresh_token"]
                self._save_tokens(self.tokens)
                return True
            else:
                print(
                    f"[SpotifyProvider] Error renovando token (HTTP {resp.status_code}): {resp.text}"
                )
                return False
        except Exception as e:
            print(f"[SpotifyProvider] Excepción al renovar token: {e}")
            return False

    def _get_valid_access_token(self) -> Optional[str]:
        """Obtiene un token de acceso válido, renovándolo automáticamente si expiró."""
        if not self.is_authenticated():
            return None

        expires_at = self.tokens.get("expires_at", 0)
        if time.time() >= expires_at:
            success = self.refresh_access_token()
            if not success:
                return None

        return self.tokens.get("access_token")

    def get_current_playback(self) -> Optional[PlaybackState]:
        """
        Consulta `GET /v1/me/player` y normaliza la respuesta.
        Retorna None si no hay reproducción activa (204 No Content o error).
        """
        token = self._get_valid_access_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}

        try:
            resp = requests.get(SPOTIFY_PLAYER_URL, headers=headers, timeout=5)

            # Caso 1: Sin reproducción activa (204 No Content)
            if resp.status_code == 204:
                return None

            # Caso 2: Token expirado imprevistamente (401 Unauthorized) -> reintentar 1 vez
            if resp.status_code == 401:
                print("[SpotifyProvider] HTTP 401 recibido. Renovando token...")
                if self.refresh_access_token():
                    token = self.tokens.get("access_token")
                    headers["Authorization"] = f"Bearer {token}"
                    resp = requests.get(SPOTIFY_PLAYER_URL, headers=headers, timeout=5)
                    if resp.status_code == 204:
                        return None
                else:
                    return None

            # Caso 3: Rate limit (429 Too Many Requests)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "2")
                print(f"[SpotifyProvider] Rate Limit 429. Retry-After: {retry_after}s")
                return None

            # Caso 4: Éxito (HTTP 200 OK)
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_playback_data(data)

            print(f"[SpotifyProvider] HTTP inesperado {resp.status_code}: {resp.text}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"[SpotifyProvider] Error de red consultando Spotify: {e}")
            return None

    def _parse_playback_data(self, data: Dict[str, Any]) -> Optional[PlaybackState]:
        """Convierte el JSON de Spotify en un PlaybackState normalizado."""
        item = data.get("item")
        if not item or data.get("currently_playing_type") != "track":
            # Puede ser anuncio, podcast o contenido sin track
            return None

        # Extraer artistas
        artists = [a.get("name", "") for a in item.get("artists", []) if a.get("name")]
        artist_name = ", ".join(artists) if artists else "Artista Desconocido"

        # Extraer álbum
        album = item.get("album", {})
        album_name = album.get("name") if album else None

        # Extraer dispositivo
        device = data.get("device", {})
        device_id = device.get("id")
        device_name = device.get("name")
        device_type = device.get("type")

        return PlaybackState(
            track_id=item.get("id"),
            title=item.get("name", "Sin título"),
            artist=artist_name,
            album=album_name,
            duration_ms=item.get("duration_ms", 0),
            progress_ms=data.get("progress_ms", 0),
            is_playing=data.get("is_playing", False),
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            observed_at=time.time(),
            timestamp_ms=data.get("timestamp"),
        )
