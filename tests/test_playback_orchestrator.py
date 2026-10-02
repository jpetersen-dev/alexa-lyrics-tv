"""
Pruebas unitarias para PlaybackOrchestrator (gestor de fuentes y ciclo de vida de Cast).
"""

from unittest.mock import MagicMock, patch
import time
import pytest

from src.playback_orchestrator import PlaybackOrchestrator
from src.sync_engine import SyncEngine
from src.cast_controller import CastManager
from src.lrclib_provider import LRCLIBLyricsProvider
from src.lyrics_models import LyricsStatus


@pytest.fixture
def orchestrator():
    lyrics_provider = MagicMock(spec=LRCLIBLyricsProvider)
    lyrics_provider.get_lyrics.return_value = MagicMock(status=LyricsStatus.NO_LYRICS, lines=[])
    engine = SyncEngine(lyrics_provider=lyrics_provider)
    cast_manager = MagicMock(spec=CastManager)
    cast_manager.is_connected = False
    return PlaybackOrchestrator(engine=engine, cast_manager=cast_manager, initial_provider="mock")


def test_orchestrator_initial_state(orchestrator):
    status = orchestrator.get_providers_status()
    assert status["active_provider"] == "mock"
    assert "mock" in status["providers"]
    assert "webhook" in status["providers"]
    assert "homeassistant" in status["providers"]
    assert "spotify" in status["providers"]
    assert status["autocast"]["enabled"] is False


def test_orchestrator_switch_provider(orchestrator):
    assert orchestrator.set_active_provider("webhook") is True
    assert orchestrator.active_provider_name == "webhook"
    assert orchestrator.set_active_provider("invalid_provider") is False
    assert orchestrator.active_provider_name == "webhook"


def test_orchestrator_webhook_flow(orchestrator):
    orchestrator.set_active_provider("webhook")
    webhook_p = orchestrator.webhook_provider

    # Enviar actualización externa
    state = webhook_p.update_playback(
        title="Bohemian Rhapsody",
        artist="Queen",
        duration_ms=354000,
        progress_ms=10000,
        is_playing=True,
    )
    assert state.title == "Bohemian Rhapsody"

    # Ejecutar tick del orquestador
    synced = orchestrator.tick()
    assert synced is not None
    assert synced.track == "Bohemian Rhapsody"
    assert synced.artist == "Queen"
    assert synced.is_playing is True


def test_orchestrator_autocast_lifecycle(orchestrator):
    orchestrator.configure_autocast(
        enabled=True,
        target_device="Living Room TV",
        idle_timeout_seconds=5.0,
    )
    orchestrator.cast_manager.connect_to_device.return_value = True
    orchestrator.cast_manager.is_connected = False

    # 1. Poner en reproducción -> Debe disparar conexión y lanzamiento
    orchestrator.set_active_provider("webhook")
    orchestrator.webhook_provider.update_playback(
        title="Hotel California",
        artist="Eagles",
        duration_ms=390000,
        progress_ms=5000,
        is_playing=True,
    )

    orchestrator.tick()
    orchestrator.cast_manager.connect_to_device.assert_called_with(
        name="Living Room TV", host=None
    )
    orchestrator.cast_manager.launch_app.assert_called_once()

    # 2. Simular pausa y expiración de inactividad
    orchestrator.cast_manager.is_connected = True
    orchestrator.webhook_provider.update_playback(
        title="Hotel California",
        artist="Eagles",
        duration_ms=390000,
        progress_ms=5000,
        is_playing=False,
    )

    # Forzar tiempo anterior
    orchestrator._last_playing_time = time.time() - 10.0
    orchestrator.tick()

    # Debe haber cerrado la aplicación y desconectado
    orchestrator.cast_manager.quit_app.assert_called_once()
    orchestrator.cast_manager.disconnect.assert_called_once()
