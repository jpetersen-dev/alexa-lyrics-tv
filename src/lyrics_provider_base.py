"""
Abstracción base para proveedores de letras de canciones.
Permite sustituir o alternar fuentes (LRCLIB, archivos locales, mocks) de forma transparente.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .lyrics_models import LyricsResult


class LyricsProvider(ABC):
    """Contrato base que cualquier proveedor de letras debe cumplir."""

    @abstractmethod
    def get_lyrics(
        self,
        artist: str,
        title: str,
        album: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> LyricsResult:
        """
        Obtiene las letras (sincronizadas o planas) para una canción dada.
        Retorna LyricsResult con estado SYNCED, UNSYNCED, NO_LYRICS o ERROR.
        """
        pass
