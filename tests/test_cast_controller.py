"""
Pruebas unitarias para el controlador de Google Cast (CastManager y LyricsCastController).
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.cast_controller import (
    CAST_NAMESPACE,
    DEFAULT_CAST_APP_ID,
    LyricsCastController,
    CastManager,
)


def test_lyrics_cast_controller_initialization():
    controller = LyricsCastController()
    assert controller.namespace == CAST_NAMESPACE
    assert controller.last_received_message is None


def test_lyrics_cast_controller_receive_message():
    controller = LyricsCastController()
    test_data = {"type": "READY", "version": "1.0.0"}
    success = controller.receive_message("READY", test_data)
    assert success is True
    assert controller.last_received_message == test_data


def test_lyrics_cast_controller_send_synced_state():
    controller = LyricsCastController()
    controller.send_message = MagicMock()

    payload = {
        "track": "Bohemian Rhapsody",
        "artist": "Queen",
        "position_ms": 12000,
        "is_playing": True,
    }
    controller.send_synced_state(payload)

    controller.send_message.assert_called_once()
    args, _ = controller.send_message.call_args
    sent_json = json.loads(args[0])
    assert sent_json["track"] == "Bohemian Rhapsody"
    assert sent_json["artist"] == "Queen"


def test_cast_manager_initial_state():
    manager = CastManager()
    assert manager.is_connected is False
    assert manager.cast_device is None
    assert manager.cast_controller is None


def test_cast_manager_discover_devices():
    mock_cc = MagicMock()
    mock_cc.name = "Living Room TV"
    mock_cc.model_name = "Chromecast Ultra"
    mock_cc.cast_info.host = "192.168.1.150"
    mock_cc.cast_info.port = 8009
    mock_cc.uuid = "1234-5678"

    with patch("pychromecast.get_chromecasts", return_value=([mock_cc], MagicMock())), \
         patch("pychromecast.stop_discovery"):
        manager = CastManager()
        devices = manager.discover_devices(timeout=1.0)
        assert len(devices) == 1
        assert devices[0]["name"] == "Living Room TV"
        assert devices[0]["host"] == "192.168.1.150"


def test_cast_manager_connect_by_host():
    mock_cc = MagicMock()
    mock_cc.name = "Living Room TV"
    mock_cc.model_name = "Chromecast"

    with patch("pychromecast.Chromecast", return_value=mock_cc):
        manager = CastManager()
        success = manager.connect_to_device(host="192.168.1.150")
        assert success is True
        assert manager.is_connected is True
        mock_cc.wait.assert_called_once()
        mock_cc.register_handler.assert_called_once()


def test_cast_manager_launch_app_and_send_state():
    mock_cc = MagicMock()
    mock_cc.app_id = "TEST_APP_123"

    with patch("pychromecast.Chromecast", return_value=mock_cc):
        manager = CastManager()
        manager.connect_to_device(host="192.168.1.150")

        # Lanzar app
        launched = manager.launch_app("TEST_APP_123", timeout=1.0)
        assert launched is True
        mock_cc.start_app.assert_called_with("TEST_APP_123")

        # Enviar estado
        with patch.object(manager.cast_controller, "send_synced_state") as mock_send:
            test_state = {"track": "Test Track", "is_playing": True}
            sent = manager.send_playback_state(test_state)
            assert sent is True
            mock_send.assert_called_with(test_state)

        # Cerrar app y desconectar
        manager.quit_app()
        mock_cc.quit_app.assert_called_once()

        manager.disconnect()
        assert manager.is_connected is False
