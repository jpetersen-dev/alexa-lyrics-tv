"""
Modelos de datos normalizados para el estado de reproducción de audio.
Desacopla la lógica del reproductor (Spotify, Alexa, etc.) del resto del sistema.
"""

from dataclasses import dataclass, asdict
from typing import Optional
import time


@dataclass
class PlaybackState:
    """
    Representa el estado instantáneo de la reproducción musical normalizada.
    """
    track_id: Optional[str]
    title: str
    artist: str
    album: Optional[str]
    duration_ms: int
    progress_ms: int
    is_playing: bool
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    observed_at: float = 0.0  # Epoch en segundos al momento de la observación local
    timestamp_ms: Optional[int] = None  # Timestamp en ms reportado por el servidor proveedor

    def __post_init__(self):
        if self.observed_at == 0.0:
            self.observed_at = time.time()

    @property
    def progress_seconds(self) -> float:
        return self.progress_ms / 1000.0

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        state_str = "▶ PLAYING" if self.is_playing else "⏸ PAUSED"
        pos_str = f"{int(self.progress_seconds // 60):02d}:{int(self.progress_seconds % 60):02d}"
        dur_str = f"{int(self.duration_seconds // 60):02d}:{int(self.duration_seconds % 60):02d}"
        dev_str = f" [{self.device_name} ({self.device_type})]" if self.device_name else ""
        return f"{state_str} | {self.artist} - '{self.title}' ({pos_str} / {dur_str}){dev_str}"
