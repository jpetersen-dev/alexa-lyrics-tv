"""
Proveedor de reproducción para Home Assistant (Alexa Media Player / Echo devices).
Consulta el estado de entidades 'media_player' a través de la API REST de Home Assistant,
permitiendo capturar lo que suena en altavoces Echo sin depender de la API de Spotify.
"""

import os
import time
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv

from .models import PlaybackState
from .provider_base import PlaybackProvider

load_dotenv()


class HomeAssistantPlaybackProvider(PlaybackProvider):
    """
    Proveedor que consulta el estado de reproducción de un altavoz Alexa
    integrado en Home Assistant (vía integración alexa_media_player).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        entity_id: Optional[str] = None,
        timeout: float = 3.0,
    ):
        self.base_url = (base_url or os.getenv("HASS_URL", "http://homeassistant.local:8123")).rstrip("/")
        self.access_token = access_token or os.getenv("HASS_TOKEN", "")
        self.entity_id = entity_id or os.getenv("HASS_ALEXA_ENTITY", "media_player.echo_dot")
        self.timeout = timeout

    def is_authenticated(self) -> bool:
        """Verifica si se ha configurado un token de larga duración de Home Assistant."""
        return bool(self.access_token)

    def get_current_playback(self) -> Optional[PlaybackState]:
        """
        Consulta GET /api/states/{entity_id} en Home Assistant y normaliza la salida.
        """
        if not self.is_authenticated():
            return None

        url = f"{self.base_url}/api/states/{self.entity_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                return None

            data = resp.json()
            state_val = data.get("state", "").lower()
            if state_val in ["off", "unavailable", "idle", "standby"]:
                return None

            attrs = data.get("attributes", {})
            title = attrs.get("media_title") or "Pista Desconocida"
            artist = attrs.get("media_artist") or "Artista Desconocido"
            album = attrs.get("media_album_name")
            duration_s = attrs.get("media_duration", 0)
            duration_ms = int(duration_s * 1000)

            # Posición en segundos reportada por HASS
            media_pos_s = attrs.get("media_position", 0)
            media_pos_ms = int(media_pos_s * 1000)

            # Compensar tiempo transcurrido desde media_position_updated_at si está disponible
            updated_at_str = attrs.get("media_position_updated_at")
            is_playing = state_val == "playing"

            return PlaybackState(
                track_id=f"{artist}_{title}".replace(" ", "_"),
                title=title,
                artist=artist,
                album=album,
                duration_ms=duration_ms,
                progress_ms=media_pos_ms,
                is_playing=is_playing,
                device_name=attrs.get("friendly_name", self.entity_id),
                device_type="echo_speaker",
                observed_at=time.time(),
            )
        except Exception:
            return None
