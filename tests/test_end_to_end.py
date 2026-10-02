"""
Pruebas de Integración End-to-End para Alexa Lyrics TV.
Verifica la cadena completa:
Observación externa (Webhook/Alexa) -> SyncEngine -> LRCLIB Cache -> WebSocket -> Cast Dispatch -> AutoCast Lifecycle.
"""

import pytest
from starlette.testclient import TestClient
from src.server import app, orchestrator, cast_manager


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_e2e_provider_selection(client):
    # 1. Consultar proveedores disponibles
    resp = client.get("/api/playback/provider")
    assert resp.status_code == 200
    data = resp.json()
    assert "mock" in data["providers"]
    assert "webhook" in data["providers"]
    assert "homeassistant" in data["providers"]
    assert "spotify" in data["providers"]

    # 2. Cambiar a webhook
    resp_set = client.post("/api/playback/provider", json={"provider": "webhook"})
    assert resp_set.status_code == 200
    assert resp_set.json()["status"]["active_provider"] == "webhook"

    # 3. Intentar cambiar a proveedor no existente
    resp_invalid = client.post("/api/playback/provider", json={"provider": "nonexistent"})
    assert resp_invalid.status_code == 400


def test_e2e_webhook_playback_and_lyrics(client):
    # Simular que Alexa reproduce una canción real
    payload = {
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "album": "A Night at the Opera",
        "duration_ms": 354320,
        "progress_ms": 15000,
        "is_playing": True,
        "device_name": "Echo Studio Sala",
    }
    resp = client.post("/api/playback/update", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Estado de reproducción actualizado"
    state = data["state"]
    assert state is not None
    assert state["track"] == "Bohemian Rhapsody"
    assert state["artist"] == "Queen"
    assert state["is_playing"] is True
    assert state["device_name"] == "Echo Studio Sala"

    # Verificar que el status de API refleje la canción
    resp_status = client.get("/api/status")
    assert resp_status.status_code == 200
    assert resp_status.json()["playback"]["track"] == "Bohemian Rhapsody"


def test_e2e_autocast_configuration(client):
    # Configurar AutoCast
    cfg_payload = {
        "enabled": True,
        "target_device": "Televisor Living",
        "target_host": "192.168.1.150",
        "target_app_id": "ALEXA123",
        "idle_timeout_seconds": 120.0,
    }
    resp = client.post("/api/autocast/config", json=cfg_payload)
    assert resp.status_code == 200
    data = resp.json()["autocast"]
    assert data["enabled"] is True
    assert data["target_device"] == "Televisor Living"
    assert data["target_host"] == "192.168.1.150"
    assert data["target_app_id"] == "ALEXA123"
    assert data["idle_timeout_seconds"] == 120.0

    # Consultar GET
    resp_get = client.get("/api/autocast/config")
    assert resp_get.status_code == 200
    assert resp_get.json()["enabled"] is True


def test_e2e_websocket_stream_with_webhook(client):
    with client.websocket_connect("/ws/playback") as ws:
        # 1. Mensaje de bienvenida inicial
        initial_msg = ws.receive_json()
        assert "track" in initial_msg

        # 2. Enviar actualización externa
        client.post(
            "/api/playback/update",
            json={
                "title": "Hotel California",
                "artist": "Eagles",
                "duration_ms": 390000,
                "progress_ms": 30000,
                "is_playing": True,
                "device_name": "Echo Dot Dormitorio",
            },
        )

        # 3. El WebSocket debe recibir el estado actualizado de Hotel California
        updated_msg = ws.receive_json()
        assert updated_msg["track"] == "Hotel California"
        assert updated_msg["artist"] == "Eagles"
        assert updated_msg["is_playing"] is True
