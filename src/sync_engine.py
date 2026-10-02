"""
Motor de Sincronización (SyncEngine).
Orquesta el proveedor de reproducción, el reloj local de alta precisión,
el proveedor de letras y el cálculo de la línea activa para emitir SyncedPlaybackState.
"""

import time
from typing import Optional, List, Callable, Dict, Any

from .models import PlaybackState
from .playback_clock import PlaybackClock
from .lyrics_models import LyricsResult, LyricsStatus, LyricLine
from .lyrics_provider_base import LyricsProvider
from .lrc_parser import get_active_line
from .sync_models import SyncedPlaybackState, SyncEvent, PlaybackEventType


class SyncEngine:
    """
    Núcleo de sincronización independiente y desacoplado de la fuente de audio.
    """

    def __init__(
        self,
        lyrics_provider: LyricsProvider,
        clock: Optional[PlaybackClock] = None,
    ):
        self.lyrics_provider = lyrics_provider
        self.clock = clock or PlaybackClock()

        # Estado interno
        self._current_track_id: Optional[str] = None
        self._current_track_title: Optional[str] = None
        self._current_track_artist: Optional[str] = None
        self._current_album: Optional[str] = None
        self._current_lyrics: LyricsResult = LyricsResult(status=LyricsStatus.NO_LYRICS)
        self._last_state: Optional[SyncedPlaybackState] = None
        self._listeners: List[Callable[[SyncEvent], None]] = []

    def add_event_listener(self, listener: Callable[[SyncEvent], None]):
        """Registra un callback para recibir eventos de transporte y letras."""
        self._listeners.append(listener)

    def _emit(self, event_type: PlaybackEventType, data: Optional[Dict[str, Any]] = None):
        event = SyncEvent(event_type=event_type, timestamp=time.time(), data=data)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"[SyncEngine] Error en listener de evento {event_type}: {e}")

    def process_observation(
        self,
        playback: Optional[PlaybackState],
        network_latency_ms: float = 0.0,
    ) -> SyncedPlaybackState:
        """
        Procesa una nueva observación recibida de un PlaybackProvider.
        """
        # Caso 1: Sin reproducción activa (204 No Content / detenido)
        if playback is None:
            self.clock.reset()
            self._current_track_id = None
            self._current_lyrics = LyricsResult(status=LyricsStatus.NO_LYRICS)
            self._emit(PlaybackEventType.PLAYBACK_STOPPED)

            state = SyncedPlaybackState(
                track="Sin reproducción",
                artist="Inactivo",
                duration_ms=0,
                position_ms=0,
                is_playing=False,
                lyrics_status="STOPPED",
                lyrics_lines=[],
                active_line_index=-1,
                active_line_text=None,
                next_line_text=None,
            )
            self._last_state = state
            return state

        # Caso 2: Cambio de canción detectado
        track_changed = False
        if playback.track_id != self._current_track_id or (
            playback.title != self._current_track_title and playback.artist != self._current_track_artist
        ):
            track_changed = True
            self._current_track_id = playback.track_id
            self._current_track_title = playback.title
            self._current_track_artist = playback.artist
            self._current_album = playback.album

            # Invalidar letras anteriores de inmediato para evitar flashes visuales
            self._current_lyrics = LyricsResult(status=LyricsStatus.LOADING)
            self._emit(
                PlaybackEventType.TRACK_CHANGED,
                {"track_id": playback.track_id, "title": playback.title, "artist": playback.artist},
            )
            self._emit(PlaybackEventType.LYRICS_LOADING)

            # Consultar nuevas letras
            new_lyrics = self.lyrics_provider.get_lyrics(
                artist=playback.artist,
                title=playback.title,
                album=playback.album,
                duration_ms=playback.duration_ms,
            )
            self._current_lyrics = new_lyrics

            if new_lyrics.has_synced:
                self._emit(PlaybackEventType.LYRICS_READY, {"lines_count": len(new_lyrics.lines)})
            else:
                self._emit(PlaybackEventType.LYRICS_UNAVAILABLE, {"status": new_lyrics.status.value})

        # Actualizar reloj de interpolación
        was_playing = self.clock.is_playing
        is_seek = self.clock.update_observation(
            progress_ms=playback.progress_ms,
            is_playing=playback.is_playing,
            duration_ms=playback.duration_ms,
            network_latency_ms=network_latency_ms,
        )

        # Emitir eventos de transporte
        if not track_changed:
            if was_playing and not playback.is_playing:
                self._emit(PlaybackEventType.PLAYBACK_PAUSED, {"position_ms": playback.progress_ms})
            elif not was_playing and playback.is_playing:
                self._emit(PlaybackEventType.PLAYBACK_RESUMED, {"position_ms": playback.progress_ms})
            elif is_seek:
                self._emit(PlaybackEventType.PLAYBACK_SEEKED, {"position_ms": playback.progress_ms})

        return self._build_synced_state(playback.device_name)

    def tick(self) -> SyncedPlaybackState:
        """
        Avanza el reloj local un paso y recalcula la línea activa sin esperar
        nuevas observaciones de red (render continuo / heartbeat).
        """
        device_name = self._last_state.device_name if self._last_state else None
        state = self._build_synced_state(device_name=device_name)
        self._emit(
            PlaybackEventType.TICK,
            {"position_ms": state.position_ms, "active_line_index": state.active_line_index},
        )
        return state

    def _build_synced_state(self, device_name: Optional[str] = None) -> SyncedPlaybackState:
        """Calcula la posición interpolada y la línea activa actual."""
        if not self._current_track_title:
            return SyncedPlaybackState(
                track="Sin reproducción",
                artist="Inactivo",
                duration_ms=0,
                position_ms=0,
                is_playing=False,
                lyrics_status="IDLE",
            )

        current_pos_ms = self.clock.get_current_position_ms()
        lyrics_lines = self._current_lyrics.lines

        active_res = get_active_line(current_pos_ms, lyrics_lines)

        lines_serialized = [l.to_dict() for l in lyrics_lines]

        state = SyncedPlaybackState(
            track=self._current_track_title,
            artist=self._current_track_artist or "Desconocido",
            album=self._current_album,
            duration_ms=self.clock.duration_ms,
            position_ms=current_pos_ms,
            is_playing=self.clock.is_playing,
            lyrics_status=(
                self._current_lyrics.status.value
                if hasattr(self._current_lyrics.status, "value")
                else str(self._current_lyrics.status)
            ),
            lyrics_lines=lines_serialized,
            active_line_index=active_res.index,
            active_line_text=active_res.line.text if active_res.line else None,
            next_line_text=active_res.next_line.text if active_res.next_line else None,
            device_name=device_name,
            generated_at=time.time(),
            reference_timestamp_ms=int(time.time() * 1000),
        )
        self._last_state = state
        return state

    @property
    def current_lyrics(self) -> LyricsResult:
        return self._current_lyrics

    @property
    def last_state(self) -> Optional[SyncedPlaybackState]:
        return self._last_state
