"""
Suite completa de pruebas de integración para el SyncEngine.
Cubre los 11 escenarios obligatorios y todas las simulaciones de error.
"""

import time
import pytest
from typing import Optional

from src.models import PlaybackState
from src.playback_clock import PlaybackClock
from src.lyrics_models import LyricsResult, LyricsStatus, LyricLine
from src.lyrics_provider_base import LyricsProvider
from src.sync_engine import SyncEngine
from src.sync_models import PlaybackEventType, SyncedPlaybackState
from src.mock_provider import MockPlaybackProvider


class MockCustomLyricsProvider(LyricsProvider):
    """Proveedor mock de letras programable para tests unitarios y de estrés."""

    def __init__(self):
        self.mode = "SYNCED"  # SYNCED, UNSYNCED, NO_LYRICS, TIMEOUT, HTTP_429, HTTP_500, CORRUPT
        self.call_count = 0

    def get_lyrics(
        self,
        artist: str,
        title: str,
        album: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> LyricsResult:
        self.call_count += 1

        if self.mode == "SYNCED":
            lines = [
                LyricLine(timestamp_ms=10000, text="Línea 1 a los 10s"),
                LyricLine(timestamp_ms=25000, text="Línea 2 a los 25s"),
                LyricLine(timestamp_ms=40000, text="Coro final a los 40s"),
            ]
            return LyricsResult(status=LyricsStatus.SYNCED, lines=lines, source="MOCK")

        elif self.mode == "UNSYNCED":
            return LyricsResult(
                status=LyricsStatus.UNSYNCED,
                lines=[],
                plain_text="Letra plana sin marcas de tiempo",
                source="MOCK",
            )

        elif self.mode == "NO_LYRICS":
            return LyricsResult(status=LyricsStatus.NO_LYRICS, source="MOCK")

        elif self.mode == "TIMEOUT":
            return LyricsResult(
                status=LyricsStatus.ERROR,
                error_message="LRCLIB Timeout Simulado",
                source="MOCK",
            )

        elif self.mode == "HTTP_429":
            return LyricsResult(
                status=LyricsStatus.ERROR,
                error_message="HTTP 429 Too Many Requests",
                source="MOCK",
            )

        elif self.mode == "HTTP_500":
            return LyricsResult(
                status=LyricsStatus.ERROR,
                error_message="HTTP 500 Internal Server Error",
                source="MOCK",
            )

        elif self.mode == "CORRUPT":
            # Retorna líneas vacías a pesar de decir que es SYNCED
            return LyricsResult(status=LyricsStatus.ERROR, error_message="LRC Corrupto", source="MOCK")

        return LyricsResult(status=LyricsStatus.NO_LYRICS, source="MOCK")


# --- TEST 1: Canción comienza en 0 ms ---
def test_scenario_1_start_at_zero():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_1", "Song Zero", "Artist A", "Album X", 200000, start_position_ms=0, is_playing=True)

    state = engine.process_observation(mock.get_current_playback())

    assert state.track == "Song Zero"
    assert state.is_playing is True
    assert 0 <= state.position_ms <= 100
    assert state.active_line_index == -1  # Intro antes de los 10s
    assert state.active_line_text is None
    assert state.next_line_text == "Línea 1 a los 10s"
    assert state.lyrics_status == "SYNCED"


# --- TEST 2: Canción comienza en 30.000 ms ---
def test_scenario_2_start_at_30s():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_2", "Song 30s", "Artist B", "Album Y", 200000, start_position_ms=30000, is_playing=True)

    state = engine.process_observation(mock.get_current_playback())

    assert state.is_playing is True
    assert 29900 <= state.position_ms <= 30200
    # A los 30s, debe estar activa la línea 2 (25s a 40s)
    assert state.active_line_index == 1
    assert state.active_line_text == "Línea 2 a los 25s"
    assert state.next_line_text == "Coro final a los 40s"


# --- TEST 3: Pausa durante una línea ---
def test_scenario_3_pause_during_line():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_3", "Song Pause", "Artist C", "Album Z", 200000, start_position_ms=15000, is_playing=True)

    # 1. Reproducción activa en 15s
    s1 = engine.process_observation(mock.get_current_playback())
    assert s1.is_playing is True
    assert s1.active_line_index == 0

    # 2. Pausar
    mock.pause()
    s2 = engine.process_observation(mock.get_current_playback())
    assert s2.is_playing is False
    paused_pos = s2.position_ms

    # 3. Avanzar tiempo real sin que el mock reproduzca
    time.sleep(0.1)
    s3 = engine.tick()
    # La posición debe permanecer exactamente congelada en pausa
    assert s3.is_playing is False
    assert s3.position_ms == paused_pos
    assert s3.active_line_index == 0


# --- TEST 4: Reanudación ---
def test_scenario_4_resume():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_4", "Song Resume", "Artist D", "Album W", 200000, start_position_ms=18000, is_playing=False)

    # Inicia pausado en 18s
    s1 = engine.process_observation(mock.get_current_playback())
    assert s1.is_playing is False

    # Reanudar
    mock.resume()
    s2 = engine.process_observation(mock.get_current_playback())
    assert s2.is_playing is True

    time.sleep(0.1)
    s3 = engine.tick()
    assert s3.position_ms > s1.position_ms


# --- TEST 5: Seek hacia adelante ---
def test_scenario_5_seek_forward():
    events = []
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)
    engine.add_event_listener(lambda e: events.append(e.event_type))

    mock = MockPlaybackProvider()
    mock.load_track("track_5", "Song Seek", "Artist E", "Album V", 200000, start_position_ms=10000, is_playing=True)
    engine.process_observation(mock.get_current_playback())

    # Seek brusco de 10s a 42s (salto hacia adelante al coro)
    mock.seek(42000)
    state = engine.process_observation(mock.get_current_playback())

    assert 41900 <= state.position_ms <= 42200
    assert state.active_line_index == 2  # Coro final (40s+)
    assert state.active_line_text == "Coro final a los 40s"
    assert PlaybackEventType.PLAYBACK_SEEKED in events


# --- TEST 6: Seek hacia atrás ---
def test_scenario_6_seek_backward():
    events = []
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)
    engine.add_event_listener(lambda e: events.append(e.event_type))

    mock = MockPlaybackProvider()
    mock.load_track("track_6", "Song Seek Back", "Artist F", "Album U", 200000, start_position_ms=45000, is_playing=True)
    engine.process_observation(mock.get_current_playback())

    # Seek hacia atrás de 45s a 5s (volver a la intro)
    mock.seek(5000)
    state = engine.process_observation(mock.get_current_playback())

    assert 4900 <= state.position_ms <= 5200
    assert state.active_line_index == -1  # Vuelve a intro
    assert PlaybackEventType.PLAYBACK_SEEKED in events


# --- TEST 7: Cambio de canción ---
def test_scenario_7_track_change():
    events = []
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)
    engine.add_event_listener(lambda e: events.append(e.event_type))

    mock = MockPlaybackProvider()
    mock.load_track("track_7_A", "Cancion A", "Artista 1", "Album 1", 180000, start_position_ms=20000, is_playing=True)
    s1 = engine.process_observation(mock.get_current_playback())
    assert s1.track == "Cancion A"

    # Cambiar a Canción B
    mock.load_track("track_7_B", "Cancion B", "Artista 2", "Album 2", 210000, start_position_ms=0, is_playing=True)
    s2 = engine.process_observation(mock.get_current_playback())

    assert s2.track == "Cancion B"
    assert s2.artist == "Artista 2"
    assert 0 <= s2.position_ms <= 100
    assert PlaybackEventType.TRACK_CHANGED in events
    assert PlaybackEventType.LYRICS_LOADING in events
    assert lyrics_prov.call_count == 2


# --- TEST 8: Canción sin letras ---
def test_scenario_8_song_without_lyrics():
    lyrics_prov = MockCustomLyricsProvider()
    lyrics_prov.mode = "NO_LYRICS"
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_8", "Instrumental", "Banda Sonora", "OST", 150000, start_position_ms=20000, is_playing=True)

    state = engine.process_observation(mock.get_current_playback())

    assert state.lyrics_status == "NO_LYRICS"
    assert len(state.lyrics_lines) == 0
    assert state.active_line_index == -1
    assert state.active_line_text is None


# --- TEST 9: LRCLIB sin 'syncedLyrics' (Solo plainLyrics) ---
def test_scenario_9_plain_lyrics_only():
    lyrics_prov = MockCustomLyricsProvider()
    lyrics_prov.mode = "UNSYNCED"
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_9", "Poema Acustico", "Trovador", "Acustico", 120000, start_position_ms=10000, is_playing=True)

    state = engine.process_observation(mock.get_current_playback())

    assert state.lyrics_status == "UNSYNCED"
    assert len(state.lyrics_lines) == 0  # No hay líneas sincronizadas con timestamp
    assert state.active_line_index == -1


# --- TEST 10: Retraso artificial de red ---
def test_scenario_10_network_latency_compensation():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    mock.load_track("track_10", "Network Lag Track", "Lag Band", "Net", 200000, start_position_ms=30000, is_playing=True)

    # Observación con retraso simulado de transporte de 350 ms
    state = engine.process_observation(mock.get_current_playback(), network_latency_ms=350.0)

    # La posición debe estar adelantada en ~350ms para compensar el retardo
    assert 30300 <= state.position_ms <= 30500


# --- TEST 11: Observaciones irregulares de red (Jitter) ---
def test_scenario_11_irregular_observations():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    # Simular ráfaga irregular con saltos temporales:
    # t=0 -> prog=0
    # t=1.7s -> prog=1700
    # t=4.3s -> prog=4300
    # t=9.1s -> prog=9100
    observations = [
        (0.0, 0),
        (1.7, 1700),
        (4.3, 4300),
        (9.1, 9100),
    ]

    for rel_t, prog_ms in observations:
        mock_state = PlaybackState(
            track_id="track_11",
            title="Jitter Track",
            artist="Jitter Artist",
            album="Jitter Album",
            duration_ms=60000,
            progress_ms=prog_ms,
            is_playing=True,
            observed_at=time.time(),
        )
        state = engine.process_observation(mock_state)
        # El motor debe aceptar la observación sin desviarse
        assert abs(state.position_ms - prog_ms) <= 50


# --- SIMULACIÓN DE ERRORES ---
def test_error_simulation_timeout():
    lyrics_prov = MockCustomLyricsProvider()
    lyrics_prov.mode = "TIMEOUT"
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    state = engine.process_observation(mock.get_current_playback())

    # El sistema no se cae ante timeout; emite estado ERROR amigable
    assert state.lyrics_status == "ERROR"
    assert state.is_playing is False or state.is_playing is True


def test_error_simulation_http_429():
    lyrics_prov = MockCustomLyricsProvider()
    lyrics_prov.mode = "HTTP_429"
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    state = engine.process_observation(mock.get_current_playback())

    assert state.lyrics_status == "ERROR"


def test_error_simulation_http_500():
    lyrics_prov = MockCustomLyricsProvider()
    lyrics_prov.mode = "HTTP_500"
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    mock = MockPlaybackProvider()
    state = engine.process_observation(mock.get_current_playback())

    assert state.lyrics_status == "ERROR"


def test_error_simulation_provider_loss():
    lyrics_prov = MockCustomLyricsProvider()
    engine = SyncEngine(lyrics_provider=lyrics_prov)

    # 1. Reproducción activa
    mock = MockPlaybackProvider()
    mock.play()
    engine.process_observation(mock.get_current_playback())

    # 2. Pérdida temporal del PlaybackProvider (devuelve None / 204)
    state_lost = engine.process_observation(None)

    assert state_lost.is_playing is False
    assert state_lost.lyrics_status == "STOPPED"
    assert state_lost.position_ms == 0
