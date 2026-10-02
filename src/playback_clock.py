"""
Reloj local de reproducción (PlaybackClock).
Proporciona una fuente de tiempo continua y resiliente mediante interpolación
monotónica local, eliminando la necesidad de saturar la red con consultas constantes.
"""

import time
from typing import Optional


class PlaybackClock:
    """
    Gestiona el avance temporal de una canción mediante anclas de tiempo.
    Calcula la posición estimada continua basándose en time.monotonic().
    """

    def __init__(self, seek_threshold_ms: int = 2500):
        self._anchor_progress_ms: int = 0
        self._anchor_monotonic: float = 0.0
        self._is_playing: bool = False
        self._duration_ms: int = 0
        self._seek_threshold_ms: int = seek_threshold_ms
        self._has_observation: bool = False

    def reset(self):
        """Reinicia el reloj a estado inicial."""
        self._anchor_progress_ms = 0
        self._anchor_monotonic = time.monotonic()
        self._is_playing = False
        self._duration_ms = 0
        self._has_observation = False

    def update_observation(
        self,
        progress_ms: int,
        is_playing: bool,
        duration_ms: int,
        network_latency_ms: float = 0.0,
    ) -> bool:
        """
        Recalibra el reloj ante una nueva observación externa.
        
        Args:
            progress_ms: Posición reportada por el reproductor.
            is_playing: True si está en reproducción, False si está en pausa.
            duration_ms: Duración total de la canción en ms.
            network_latency_ms: Estimación del retraso de transporte entre origen y recepción.
            
        Returns:
            bool: True si se detectó un salto brusco (seek) o cambio de estado.
        """
        now_mono = time.monotonic()
        was_playing = self._is_playing
        prev_estimated_pos = self.get_current_position_ms()

        self._duration_ms = max(0, duration_ms)
        self._is_playing = is_playing

        # Si el audio está reproduciéndose, compensamos la latencia de transporte
        # estimada para anclar la posición real al momento de recepción
        adjusted_progress = progress_ms
        if is_playing and network_latency_ms > 0:
            adjusted_progress = int(progress_ms + network_latency_ms)

        adjusted_progress = max(0, min(adjusted_progress, self._duration_ms))

        # Detectar si ocurrió un seek (diferencia significativa entre lo esperado y lo observado)
        is_seek = False
        if self._has_observation:
            diff_ms = abs(adjusted_progress - prev_estimated_pos)
            if diff_ms > self._seek_threshold_ms or (adjusted_progress < prev_estimated_pos and is_playing):
                is_seek = True

        self._anchor_progress_ms = adjusted_progress
        self._anchor_monotonic = now_mono
        self._has_observation = True

        return is_seek or (was_playing != is_playing)

    def get_current_position_ms(self) -> int:
        """
        Calcula la posición estimada actual en milisegundos.
        - Si está pausado: devuelve exactamente la posición anclada (congelada).
        - Si está reproduciendo: añade el tiempo monotónico transcurrido.
        """
        if not self._has_observation:
            return 0

        if not self._is_playing:
            return self._anchor_progress_ms

        elapsed_ms = int((time.monotonic() - self._anchor_monotonic) * 1000)
        estimated_ms = self._anchor_progress_ms + elapsed_ms

        return min(self._duration_ms, max(0, estimated_ms))

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def has_observation(self) -> bool:
        return self._has_observation
