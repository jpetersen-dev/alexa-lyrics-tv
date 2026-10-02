"""
Pruebas unitarias para HomeAssistantPlaybackProvider.
"""

from unittest.mock import patch, MagicMock
import pytest
from src.hass_provider import HomeAssistantPlaybackProvider


def test_hass_provider_not_authenticated():
    provider = HomeAssistantPlaybackProvider(access_token="")
    assert provider.is_authenticated() is False
    assert provider.get_current_playback() is None


def test_hass_provider_idle_or_off():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"state": "off", "attributes": {}}

    with patch("requests.get", return_value=mock_resp):
        provider = HomeAssistantPlaybackProvider(
            base_url="http://test-hass:8123",
            access_token="fake_token",
            entity_id="media_player.alexa",
        )
        assert provider.is_authenticated() is True
        state = provider.get_current_playback()
        assert state is None


def test_hass_provider_playing():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "state": "playing",
        "attributes": {
            "media_title": "Hotel California",
            "media_artist": "Eagles",
            "media_album_name": "Hotel California",
            "media_duration": 390.0,
            "media_position": 45.0,
            "friendly_name": "Echo Dot Peter",
        },
    }

    with patch("requests.get", return_value=mock_resp):
        provider = HomeAssistantPlaybackProvider(
            base_url="http://test-hass:8123",
            access_token="fake_token",
            entity_id="media_player.alexa",
        )
        state = provider.get_current_playback()
        assert state is not None
        assert state.title == "Hotel California"
        assert state.artist == "Eagles"
        assert state.album == "Hotel California"
        assert state.duration_ms == 390000
        assert state.progress_ms == 45000
        assert state.is_playing is True
        assert state.device_name == "Echo Dot Peter"
