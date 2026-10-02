"""
Proveedor de reproducción simulado (MockPlaybackProvider).
Permite emular escenarios completos de reproducción musical (play, pause, seek,
cambio de pista) para pruebas reproducibles sin depender de APIs externas.
"""

import time
from typing import Optional, List, Dict, Any
from .models import PlaybackState
from .provider_base import PlaybackProvider


class MockPlaybackProvider(PlaybackProvider):
    """
    Simulador determinista de reproducción musical que implementa PlaybackProvider.
    """

    def __init__(self, tracks: Optional[List[Dict[str, Any]]] = None):
        self._tracks = tracks or [
            {
                "track_id": "mock_queen_bohemian",
                "title": "Bohemian Rhapsody",
                "artist": "Queen",
                "album": "A Night at the Opera",
                "duration_ms": 354320,
            },
            {
                "track_id": "mock_hotel_california",
                "title": "Hotel California",
                "artist": "Eagles",
                "album": "Hotel California",
                "duration_ms": 391000,
            },
            {
                "track_id": "mock_no_lyrics_track",
                "title": "Cancion Sin Letra Instrumental",
                "artist": "Artista Ficticio",
                "album": "Album Vacio",
                "duration_ms": 180000,
            },
        ]
        self._current_index = 0
        self._is_playing = False
        self._current_position_ms = 0
        self._last_time_monotonic = time.monotonic()
        self._active = True

        # Cargar primera pista en pausa por defecto
        self._load_current_track()

    def _load_current_track(self):
        track = self._tracks[self._current_index]
        self._current_track = track
        self._current_position_ms = 0
        self._last_time_monotonic = time.monotonic()

    def is_authenticated(self) -> bool:
        return True

    def _update_position(self):
        """Actualiza la posición interna según el tiempo monotónico transcurrido."""
        now = time.monotonic()
        if self._is_playing and self._active:
            elapsed_ms = int((now - self._last_time_monotonic) * 1000)
            self._current_position_ms = min(
                self._current_track["duration_ms"],
                self._current_position_ms + elapsed_ms,
            )
            # Si termina la canción, pausar al final
            if self._current_position_ms >= self._current_track["duration_ms"]:
                self._is_playing = False
        self._last_time_monotonic = now

    def get_current_playback(self) -> Optional[PlaybackState]:
        """Devuelve el PlaybackState normalizado actual."""
        if not self._active:
            return None

        self._update_position()

        return PlaybackState(
            track_id=self._current_track["track_id"],
            title=self._current_track["title"],
            artist=self._current_track["artist"],
            album=self._current_track.get("album"),
            duration_ms=self._current_track["duration_ms"],
            progress_ms=self._current_position_ms,
            is_playing=self._is_playing,
            device_id="mock_device_01",
            device_name="Echo Mock Virtual",
            device_type="Speaker",
            observed_at=time.time(),
            timestamp_ms=int(time.time() * 1000),
        )

    # Métodos de control para pruebas
    def play(self, start_position_ms: int = 0):
        self._current_position_ms = start_position_ms
        self._is_playing = True
        self._active = True
        self._last_time_monotonic = time.monotonic()

    def pause(self):
        self._update_position()
        self._is_playing = False

    def resume(self):
        self._update_position()
        self._is_playing = True
        self._last_time_monotonic = time.monotonic()

    def seek(self, position_ms: int):
        self._last_time_monotonic = time.monotonic()
        self._current_position_ms = max(
            0, min(position_ms, self._current_track["duration_ms"])
        )

    def next_track(self, custom_track: Optional[Dict[str, Any]] = None):
        if custom_track:
            self._tracks.append(custom_track)
            self._current_index = len(self._tracks) - 1
        else:
            self._current_index = (self._current_index + 1) % len(self._tracks)
        self._load_current_track()
        self._is_playing = True

    def load_track(
        self,
        track_id: str,
        title: str,
        artist: str,
        album: Optional[str],
        duration_ms: int,
        start_position_ms: int = 0,
        is_playing: bool = True,
    ):
        self._current_track = {
            "track_id": track_id,
            "title": title,
            "artist": artist,
            "album": album,
            "duration_ms": duration_ms,
        }
        self._current_position_ms = start_position_ms
        self._is_playing = is_playing
        self._active = True
        self._last_time_monotonic = time.monotonic()

    def stop(self):
        """Simula que el altavoz quedó inactivo (204 No Content)."""
        self._active = False
        self._is_playing = False
