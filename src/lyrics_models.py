"""
Modelos de datos para letras de canciones y resultados de sincronización.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class LyricsStatus(str, Enum):
    SYNCED = "SYNCED"        # Letra sincronizada línea a línea con timestamps
    UNSYNCED = "UNSYNCED"    # Letra plana disponible sin marcas de tiempo
    NO_LYRICS = "NO_LYRICS"  # Sin letras disponibles en el proveedor
    LOADING = "LOADING"      # Búsqueda en progreso
    ERROR = "ERROR"          # Fallo de red o error de consulta


@dataclass
class LyricLine:
    """Una línea individual de letra con su marca de tiempo exacta."""
    timestamp_ms: int
    text: str

    def to_dict(self) -> dict:
        return {"timestamp_ms": self.timestamp_ms, "text": self.text}


@dataclass
class LyricsResult:
    """Resultado devuelto por un LyricsProvider."""
    status: LyricsStatus
    lines: List[LyricLine] = field(default_factory=list)
    plain_text: Optional[str] = None
    source: str = "UNKNOWN"
    is_cached: bool = False
    error_message: Optional[str] = None

    @property
    def has_synced(self) -> bool:
        return self.status == LyricsStatus.SYNCED and len(self.lines) > 0


@dataclass
class ActiveLineResult:
    """Resultado del cálculo determinista de la línea activa actual."""
    index: int  # -1 si estamos en intro antes del primer verso
    line: Optional[LyricLine] = None
    next_line: Optional[LyricLine] = None
    is_intro: bool = False
    is_outro: bool = False
