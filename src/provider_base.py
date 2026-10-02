"""
Clase base abstracta para proveedores de reproducción de música.
Permite intercambiar fuentes (Spotify, Home Assistant, Custom Skill) sin alterar el resto del sistema.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .models import PlaybackState


class PlaybackProvider(ABC):
    """
    Contrato base que todo adaptador de reproducción debe implementar.
    """

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Verifica si el proveedor cuenta con credenciales y tokens válidos."""
        pass

    @abstractmethod
    def get_current_playback(self) -> Optional[PlaybackState]:
        """
        Obtiene el estado actual de reproducción normalizado.
        Retorna None si no hay reproducción activa (e.g. 204 No Content).
        """
        pass
