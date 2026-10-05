"""
Suite de Pruebas de Caos y Resiliencia (Fase 6 — Robustez y Recuperación ante Fallos).
Valida tolerancia a caídas de red, canciones sin letra, apagado imprevisto de Chromecast,
fallos en Home Assistant y fluctuaciones rápidas de transporte.
"""

import time
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.lrclib_provider import LRCLIBLyricsProvider
from src.lyrics_models import LyricsStatus, LyricsResult
from src.sync_engine import SyncEngine
from src.playback_clock import PlaybackClock
from src.models import PlaybackState
from src.cast_controller import CastManager
from src.playback_orchestrator import PlaybackOrchestrator
from src.hass_provider import HomeAssistantPlaybackProvider
from src.webhook_provider import WebhookPlaybackProvider


# -------------------------------------------------------------
# 1. Tolerancia a Cortes de Red en Búsqueda de Letras
# -------------------------------------------------------------
def test_network_outage_cached_lyrics_fallback(tmp_path):
    """
    Si Internet se cae, pero la canción ya estaba en la caché SQLite local,
    debe servir la letra sincronizada sin error.
    """
    db_file = tmp_path / "offline_cache.db"
    provider = LRCLIBLyricsProvider(db_path=str(db_file))

    # Precargar en caché simulando una reproducción previa
    provider._save_to_cache(
        cache_key="queen___bohemian rhapsody",
        artist="Queen",
        title="Bohemian Rhapsody",
        album="A Night at the Opera",
        duration_ms=354000,
        status=LyricsStatus.SYNCED,
        synced_lyrics="[00:01.00] Is this the real life?\n[00:05.00] Is this just fantasy?",
        plain_lyrics="Is this the real life? Is this just fantasy?",
    )

    # Simular caída total de red en requests.get
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Network is down")):
        result = provider.get_lyrics(artist="Queen", title="Bohemian Rhapsody")

    assert result.status == LyricsStatus.SYNCED
    assert result.is_cached is True
    assert len(result.lines) == 2
    assert result.lines[0].text == "Is this the real life?"


def test_network_outage_uncached_graceful_error(tmp_path):
    """
    Si Internet se cae y la canción NO está en caché, debe retornar ERROR limpiamente
    sin propagar excepciones no controladas ni colapsar el SyncEngine.
    """
    db_file = tmp_path / "empty_cache.db"
    provider = LRCLIBLyricsProvider(db_path=str(db_file))

    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        result = provider.get_lyrics(artist="Daft Punk", title="Around the World")

        assert result.status == LyricsStatus.ERROR
        assert "Timeout" in result.error_message

        # Verificar que el SyncEngine procesa este estado sin lanzar excepción
        engine = SyncEngine(lyrics_provider=provider)
        playback = PlaybackState(
            track_id="daft_punk_around_the_world",
            title="Around the World",
            artist="Daft Punk",
            album="Homework",
            duration_ms=420000,
            progress_ms=10000,
            is_playing=True,
        )

        synced_state = engine.process_observation(playback)
        assert synced_state.lyrics_status == "ERROR"
        assert synced_state.lyrics_lines == []
        assert synced_state.active_line_index == -1
        assert synced_state.is_playing is True


# -------------------------------------------------------------
# 2. Canción Instrumental o Sin Letra en Catálogo
# -------------------------------------------------------------
def test_instrumental_track_handling(tmp_path):
    """
    Una canción instrumental o no catalogada en LRCLIB debe producir
    un estado NO_LYRICS estable en el televisor sin romper el reloj.
    """
    db_file = tmp_path / "instrumental.db"
    provider = LRCLIBLyricsProvider(db_path=str(db_file))

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = []

    with patch("requests.get", return_value=mock_resp):
        result = provider.get_lyrics(artist="Ludovico Einaudi", title="Nuvole Bianche")

    assert result.status == LyricsStatus.NO_LYRICS
    assert result.lines == []

    engine = SyncEngine(lyrics_provider=provider)
    playback = PlaybackState(
        track_id="einaudi_nuvole_bianche",
        title="Nuvole Bianche",
        artist="Ludovico Einaudi",
        album=None,
        duration_ms=360000,
        progress_ms=15000,
        is_playing=True,
    )

    state = engine.process_observation(playback)
    assert state.lyrics_status == "NO_LYRICS"
    assert state.active_line_index == -1
    assert state.active_line_text is None
    assert state.track == "Nuvole Bianche"


# -------------------------------------------------------------
# 3. Resiliencia de Desconexión / Apagado de Chromecast
# -------------------------------------------------------------
def test_cast_disconnect_on_send_error():
    """
    Si el televisor se apaga o el socket de Cast falla durante la transmisión,
    debe invocar disconnect() y poner is_connected en False sin lanzar excepción.
    """
    cm = CastManager()
    cm._is_connected = True
    cm.cast_controller = MagicMock()
    cm.cast_controller.send_synced_state.side_effect = BrokenPipeError("Socket closed by remote peer")

    success = cm.send_playback_state({"track": "Test Track"})
    assert success is False
    assert cm.is_connected is False


def test_cast_disconnect_on_keep_alive_error():
    """
    Si el keep-alive falla por corte de red hacia el Chromecast, debe liberar la conexión.
    """
    cm = CastManager()
    cm._is_connected = True
    cm.cast_controller = MagicMock()
    cm.cast_controller.send_message.side_effect = ConnectionResetError("Connection lost")

    success = cm.send_keep_alive()
    assert success is False
    assert cm.is_connected is False


def test_orchestrator_retry_when_chromecast_offline():
    """
    Si el Chromecast está fuera de línea al iniciar la música, el orquestador no crashea
    y reintenta periódicamente tras el periodo de throttle.
    """
    lyrics_p = MagicMock(spec=LRCLIBLyricsProvider)
    lyrics_p.get_lyrics.return_value = LyricsResult(status=LyricsStatus.NO_LYRICS, lines=[])
    engine = SyncEngine(lyrics_provider=lyrics_p)

    cast_mock = MagicMock(spec=CastManager)
    cast_mock.is_connected = False
    # Primer intento falla (Chromecast apagado)
    cast_mock.connect_to_device.return_value = False

    orch = PlaybackOrchestrator(engine=engine, cast_manager=cast_mock, initial_provider="webhook")
    orch.configure_autocast(enabled=True, target_device="TV Off")

    orch.webhook_provider.update_playback(
        title="Test Song",
        artist="Test Artist",
        duration_ms=200000,
        progress_ms=1000,
        is_playing=True,
    )

    # 1. Primer tick: intenta conectar y falla limpiamente
    orch.tick()
    assert cast_mock.connect_to_device.call_count == 1
    assert cast_mock.launch_app.call_count == 0

    # 2. Segundo tick inmediato (< 10 segundos): throttle evita saturar con otro intento
    orch.tick()
    assert cast_mock.connect_to_device.call_count == 1

    # 3. Transcurren 12 segundos y el Chromecast ahora enciende
    orch._last_connect_attempt_time = time.time() - 12.0
    cast_mock.connect_to_device.return_value = True

    orch.tick()
    # Se debe haber disparado el segundo intento de conexión y el lanzamiento
    assert cast_mock.connect_to_device.call_count == 2
    assert cast_mock.launch_app.call_count == 1


# -------------------------------------------------------------
# 4. Tolerancia a Errores de Home Assistant
# -------------------------------------------------------------
def test_hass_provider_network_or_500_error():
    """
    Si Home Assistant arroja un 500 Internal Server Error o timeout,
    el proveedor debe retornar None de inmediato sin quebrar el daemon.
    """
    hass = HomeAssistantPlaybackProvider(
        base_url="http://hass.local:8123",
        access_token="valid_token",
        entity_id="media_player.kitchen_echo",
    )

    with patch("requests.get", side_effect=requests.exceptions.ReadTimeout("HASS took too long")):
        playback = hass.get_current_playback()
        assert playback is None

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("requests.get", return_value=mock_resp):
        playback = hass.get_current_playback()
        assert playback is None


def test_hass_provider_idle_states():
    """
    Si el altavoz Alexa en Home Assistant está en reposo o apagado, retorna None.
    """
    hass = HomeAssistantPlaybackProvider(
        base_url="http://hass.local:8123",
        access_token="valid_token",
        entity_id="media_player.kitchen_echo",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"state": "standby", "attributes": {}}

    with patch("requests.get", return_value=mock_resp):
        assert hass.get_current_playback() is None


# -------------------------------------------------------------
# 5. Robustez ante Fluctuaciones Rápidas (Play/Pause Jitter)
# -------------------------------------------------------------
def test_rapid_play_pause_jitter():
    """
    Alternar rápidamente entre Play y Pause 20 veces consecutivas no debe
    provocar que el reloj retroceda o genere excepciones de estado.
    """
    clock = PlaybackClock()
    progress = 50000

    for i in range(20):
        is_playing = (i % 2 == 0)
        clock.update_observation(
            progress_ms=progress,
            is_playing=is_playing,
            duration_ms=300000,
        )
        pos = clock.get_current_position_ms()
        assert pos >= progress
        time.sleep(0.01)

    assert clock.duration_ms == 300000


# -------------------------------------------------------------
# 6. Webhook con Datos Extremos o Incompletos
# -------------------------------------------------------------
def test_webhook_edge_case_data():
    """
    Verifica que el WebhookPlaybackProvider tolere duraciones en cero o strings vacíos.
    """
    webhook = WebhookPlaybackProvider()
    state = webhook.update_playback(
        title="Unknown Track",
        artist="",
        duration_ms=0,
        progress_ms=-50,
        is_playing=True,
    )

    assert state.title == "Unknown Track"
    assert state.duration_ms == 0
    assert webhook.get_current_playback() is not None


# -------------------------------------------------------------
# 7. Reinicio Imprevisto del Daemon (Recuperación de Sesión)
# -------------------------------------------------------------
def test_daemon_reconnects_active_session_on_startup(tmp_path):
    """
    Si el daemon se reinicia mientras hay música sonando en Alexa,
    al arrancar debe detectar la reproducción de inmediato y reenganchar Cast.
    """
    from src.config_manager import ConfigManager
    config_file = tmp_path / "daemon_reboot_config.json"
    cm = ConfigManager(config_path=str(config_file))
    cm.set("autocast_enabled", True)
    cm.set("target_cast_device", "Living Room TV")
    cm.set("default_provider", "webhook")

    lyrics_p = MagicMock(spec=LRCLIBLyricsProvider)
    lyrics_p.get_lyrics.return_value = LyricsResult(status=LyricsStatus.NO_LYRICS, lines=[])
    engine = SyncEngine(lyrics_provider=lyrics_p)

    cast_mock = MagicMock(spec=CastManager)
    cast_mock.is_connected = False
    cast_mock.connect_to_device.return_value = True

    # Inicializar orquestador simulando arranque del daemon
    orch = PlaybackOrchestrator(
        engine=engine,
        cast_manager=cast_mock,
        config_manager=cm,
    )

    # Simular que el proveedor activo ya tiene música reproduciéndose
    orch.webhook_provider.update_playback(
        title="Bohemian Rhapsody",
        artist="Queen",
        duration_ms=354000,
        progress_ms=45000,
        is_playing=True,
    )

    # Primer ciclo de reloj del daemon recién arrancado
    state = orch.tick()

    assert state is not None
    assert state.is_playing is True
    # Verificación: conectó a Chromecast y lanzó la app de inmediato
    cast_mock.connect_to_device.assert_called_with(name="Living Room TV", host=None)
    cast_mock.launch_app.assert_called_once()
    cast_mock.send_playback_state.assert_called_once()

