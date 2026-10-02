"""
Proveedor de reproducción basado en Webhooks (HTTP Push).
Permite que scripts externos, integraciones de Home Assistant,
Node-RED o Custom Skills de Alexa envíen el estado de reproducción actual
directamente al daemon vía peticiones HTTP POST.
"""

import time
from typing import Optional, Dict, Any
from .models import PlaybackState
from .provider_base import PlaybackProvider


class WebhookPlaybackProvider(PlaybackProvider):
    """
    Proveedor que almacena el último estado de reproducción recibido
    a través de un endpoint HTTP REST/Webhook.
    """

    def __init__(self, ttl_seconds: float = 600.0):
        self._current_state: Optional[PlaybackState] = None
        self._last_update_time: float = 0.0
        self.ttl_seconds = ttl_seconds

    def is_authenticated(self) -> bool:
        """El proveedor webhook no requiere autenticación externa."""
        return True

    def get_current_playback(self) -> Optional[PlaybackState]:
        """
        Retorna el último estado recibido. Si ha transcurrido más del TTL
        sin actualizaciones y el estado no es 'playing', retorna None.
        """
        if not self._current_state:
            return None

        # Si expiró el TTL por falta de actividad
        if time.time() - self._last_update_time > self.ttl_seconds:
            return None

        return self._current_state

    def update_playback(
        self,
        title: str,
        artist: str,
        album: Optional[str] = None,
        duration_ms: int = 0,
        progress_ms: int = 0,
        is_playing: bool = True,
        device_name: Optional[str] = "Alexa Echo",
        track_id: Optional[str] = None,
    ) -> PlaybackState:
        """
        Actualiza el estado interno a partir de datos recibidos por webhook.
        """
        tid = track_id or f"{artist}_{title}".replace(" ", "_").lower()
        state = PlaybackState(
            track_id=tid,
            title=title,
            artist=artist,
            album=album,
            duration_ms=duration_ms,
            progress_ms=progress_ms,
            is_playing=is_playing,
            device_name=device_name,
            device_type="echo_speaker",
            observed_at=time.time(),
        )
        self._current_state = state
        self._last_update_time = time.time()
        return state

    def clear(self) -> None:
        """Limpia el estado activo."""
        self._current_state = None
        self._last_update_time = 0.0
