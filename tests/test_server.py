"""
Tests para la capa de transporte FastAPI y WebSockets (src/server.py).
"""

import pytest
from starlette.testclient import TestClient
from src.server import app


@pytest.fixture
def client():
    # Usar TestClient como context manager para activar el lifespan
    with TestClient(app) as test_client:
        yield test_client


def test_api_status(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert "playback" in data
    assert data["playback"]["track"] != ""


def test_api_mock_controls(client):
    # 1. Pausa
    resp_pause = client.post("/api/mock/pause")
    assert resp_pause.status_code == 200
    assert resp_pause.json()["state"]["is_playing"] is False

    # 2. Reanudar
    resp_resume = client.post("/api/mock/resume")
    assert resp_resume.status_code == 200
    assert resp_resume.json()["state"]["is_playing"] is True

    # 3. Seek a 30s
    resp_seek = client.post("/api/mock/seek", json={"position_ms": 30000})
    assert resp_seek.status_code == 200
    assert 29900 <= resp_seek.json()["state"]["position_ms"] <= 30200

    # 4. Siguiente canción
    resp_next = client.post("/api/mock/next")
    assert resp_next.status_code == 200
    assert resp_next.json()["state"]["track"] != ""


def test_websocket_playback_initial_state(client):
    # Conexión WebSocket mediante TestClient
    with client.websocket_connect("/ws/playback") as websocket:
        # Al conectar, el servidor debe enviar inmediatamente el estado actual
        data = websocket.receive_json()
        assert "track" in data
        assert "position_ms" in data
        assert "lyrics_status" in data
        assert "active_line_index" in data
