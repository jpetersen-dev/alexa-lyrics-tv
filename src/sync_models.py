"""
Modelos de sincronización y contrato de salida hacia Chromecast (CAF v3).
Desacopla completamente el Sync Engine de cualquier detalle de Spotify, Alexa o LRCLIB.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
import time


class PlaybackEventType(str, Enum):
    TRACK_CHANGED = "TRACK_CHANGED"
    PLAYBACK_STARTED = "PLAYBACK_STARTED"
    PLAYBACK_PAUSED = "PLAYBACK_PAUSED"
    PLAYBACK_RESUMED = "PLAYBACK_RESUMED"
    PLAYBACK_SEEKED = "PLAYBACK_SEEKED"
    PLAYBACK_STOPPED = "PLAYBACK_STOPPED"
    LYRICS_LOADING = "LYRICS_LOADING"
    LYRICS_READY = "LYRICS_READY"
    LYRICS_UNAVAILABLE = "LYRICS_UNAVAILABLE"
    TICK = "TICK"


@dataclass
class SyncEvent:
    """Evento emitido internamente por el motor de sincronización."""
    event_type: PlaybackEventType
    timestamp: float = field(default_factory=time.time)
    data: Optional[Dict[str, Any]] = None


@dataclass
class SyncedPlaybackState:
    """
    Contrato canónico de salida emitido hacia el Cast Custom Web Receiver en TV.
    El receptor utiliza este payload para calcular el progreso a 60 fps y renderizar
    las letras sin necesidad de saber quién originó la reproducción.
    """
    track: str
    artist: str
    duration_ms: int
    position_ms: int
    is_playing: bool
    lyrics_status: str  # SYNCED | UNSYNCED | NO_LYRICS | LOADING | ERROR
    lyrics_lines: List[Dict[str, Any]] = field(default_factory=list)
    active_line_index: int = -1
    active_line_text: Optional[str] = None
    next_line_text: Optional[str] = None
    album: Optional[str] = None
    device_name: Optional[str] = None
    generated_at: float = field(default_factory=time.time)
    reference_timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        icon = "▶" if self.is_playing else "⏸"
        pos_s = self.position_ms / 1000.0
        dur_s = self.duration_ms / 1000.0
        active_txt = f"'{self.active_line_text}'" if self.active_line_text else "(Intro / Sin letra)"
        return (
            f"{icon} [{pos_s:5.1f}s / {dur_s:5.1f}s] {self.artist} - '{self.track}' | "
            f"Línea #{self.active_line_index}: {active_txt}"
        )
