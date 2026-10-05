"""
Pruebas de ciclo de vida completo (Phase 5 - Lifecycle Automation & Background Service).
Valida la persistencia de configuración, keep-alive periódico y auto-cierre tras inactividad.
"""

import time
from unittest.mock import MagicMock
import pytest

from src.sync_engine import SyncEngine
from src.cast_controller import CastManager
from src.config_manager import ConfigManager
from src.playback_orchestrator import PlaybackOrchestrator
from src.lrclib_provider import LRCLIBLyricsProvider
from src.lyrics_models import LyricsStatus


@pytest.fixture
def mock_engine():
    lyrics_provider = MagicMock(spec=LRCLIBLyricsProvider)
    lyrics_provider.get_lyrics.return_value = MagicMock(status=LyricsStatus.NO_LYRICS, lines=[])
    return SyncEngine(lyrics_provider=lyrics_provider)


@pytest.fixture
def mock_cast_manager():
    cast = MagicMock(spec=CastManager)
    cast.is_connected = False
    cast.connect_to_device.return_value = True
    cast.launch_app.return_value = True
    cast.send_keep_alive.return_value = True
    return cast


def test_lifecycle_persistence_integration(tmp_path, mock_engine, mock_cast_manager):
    config_file = tmp_path / "lifecycle_config.json"
    cm = ConfigManager(config_path=str(config_file))
    
    orch = PlaybackOrchestrator(
        engine=mock_engine,
        cast_manager=mock_cast_manager,
        config_manager=cm,
    )

    # 1. Cambiar proveedor -> debe guardarse en config.json
    orch.set_active_provider("webhook")
    assert cm.get("default_provider") == "webhook"

    # 2. Configurar AutoCast -> debe guardarse en config.json
    orch.configure_autocast(
        enabled=True,
        target_device="Living Room TV",
        idle_timeout_seconds=60.0,
    )
    assert cm.get("autocast_enabled") is True
    assert cm.get("target_cast_device") == "Living Room TV"
    assert cm.get("idle_timeout_seconds") == 60.0

    # 3. Nuevo orquestador con el mismo archivo de config debe heredar los parámetros
    cm_reload = ConfigManager(config_path=str(config_file))
    orch2 = PlaybackOrchestrator(
        engine=mock_engine,
        cast_manager=mock_cast_manager,
        config_manager=cm_reload,
    )
    assert orch2.active_provider_name == "webhook"
    assert orch2.auto_cast_enabled is True
    assert orch2.target_cast_device == "Living Room TV"
    assert orch2.idle_timeout_seconds == 60.0


def test_lifecycle_keep_alive(mock_engine, mock_cast_manager):
    orch = PlaybackOrchestrator(
        engine=mock_engine,
        cast_manager=mock_cast_manager,
        initial_provider="mock",
    )
    orch.keep_alive_interval_seconds = 10.0
    mock_cast_manager.is_connected = True

    # 1. Primer tick con conectado
    orch.tick()
    assert mock_cast_manager.send_keep_alive.call_count == 1

    # 2. Inmediatamente otro tick: aún no pasaron 10s -> no envía otro keep alive
    orch.tick()
    assert mock_cast_manager.send_keep_alive.call_count == 1

    # 3. Forzar tiempo transcurrido > 10s
    orch._last_keep_alive_time = time.time() - 15.0
    orch.tick()
    assert mock_cast_manager.send_keep_alive.call_count == 2


def test_lifecycle_full_flow(tmp_path, mock_engine, mock_cast_manager):
    config_file = tmp_path / "flow_config.json"
    cm = ConfigManager(config_path=str(config_file))

    orch = PlaybackOrchestrator(
        engine=mock_engine,
        cast_manager=mock_cast_manager,
        config_manager=cm,
    )
    orch.configure_autocast(
        enabled=True,
        target_device="Chromecast TV",
        idle_timeout_seconds=5.0,
    )

    # 1. Estado inicial inactivo
    orch.set_active_provider("webhook")
    mock_cast_manager.is_connected = False

    # 2. Empieza la música (Play)
    orch.webhook_provider.update_playback(
        title="Don't Stop Me Now",
        artist="Queen",
        duration_ms=210000,
        progress_ms=1000,
        is_playing=True,
    )
    state = orch.tick()
    assert state.is_playing is True
    # Auto-lanzamiento disparado
    mock_cast_manager.connect_to_device.assert_called_with(name="Chromecast TV", host=None)
    mock_cast_manager.launch_app.assert_called_once()

    # 3. La TV ahora está conectada
    mock_cast_manager.is_connected = True

    # 4. Se pausa la música (Pause)
    orch.webhook_provider.update_playback(
        title="Don't Stop Me Now",
        artist="Queen",
        duration_ms=210000,
        progress_ms=30000,
        is_playing=False,
    )
    state2 = orch.tick()
    assert state2.is_playing is False
    # Aún no expiró el timeout -> no debe haber cerrado la app
    assert mock_cast_manager.quit_app.call_count == 0

    # 5. Simular inactividad prolongada (10 segundos > 5.0s timeout)
    orch._last_playing_time = time.time() - 10.0
    orch.tick()
    # Debe haber cerrado la app y desconectado
    mock_cast_manager.quit_app.assert_called_once()
    mock_cast_manager.disconnect.assert_called_once()
