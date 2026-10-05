"""
Pruebas unitarias para ConfigManager y los endpoints /api/config.
"""

import os
import json
import pytest
from starlette.testclient import TestClient

from src.config_manager import ConfigManager, DEFAULT_CONFIG
from src.server import app


def test_config_manager_defaults(tmp_path):
    config_file = tmp_path / "test_config.json"
    cm = ConfigManager(config_path=str(config_file))
    
    assert cm.get("default_provider") == "mock"
    assert cm.get("autocast_enabled") is False
    assert cm.get("idle_timeout_seconds") == 180.0
    assert cm.get("keep_alive_interval_seconds") == 15.0


def test_config_manager_save_and_reload(tmp_path):
    config_file = tmp_path / "test_config.json"
    cm = ConfigManager(config_path=str(config_file))
    
    cm.set("default_provider", "webhook")
    cm.set("autocast_enabled", True)
    cm.set("target_cast_device", "Samsung Frame TV")
    cm.set("idle_timeout_seconds", 120.0)
    assert cm.save() is True
    
    assert os.path.exists(config_file)
    
    # Recargar desde disco
    cm2 = ConfigManager(config_path=str(config_file))
    assert cm2.get("default_provider") == "webhook"
    assert cm2.get("autocast_enabled") is True
    assert cm2.get("target_cast_device") == "Samsung Frame TV"
    assert cm2.get("idle_timeout_seconds") == 120.0


def test_config_manager_update(tmp_path):
    config_file = tmp_path / "test_config.json"
    cm = ConfigManager(config_path=str(config_file))
    
    cm.update({
        "target_cast_host": "192.168.1.150",
        "hass_url": "http://192.168.1.50:8123",
    })
    cm.save()
    
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["target_cast_host"] == "192.168.1.150"
        assert data["hass_url"] == "http://192.168.1.50:8123"


def test_api_config_endpoints():
    client = TestClient(app)
    
    # 1. GET /api/config
    resp = client.get("/api/config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert "default_provider" in cfg
    assert "autocast_enabled" in cfg
    assert "idle_timeout_seconds" in cfg

    # 2. POST /api/config
    resp = client.post("/api/config", json={
        "idle_timeout_seconds": 90.0,
        "keep_alive_interval_seconds": 20.0,
    })
    assert resp.status_code == 200
    updated_cfg = resp.json()["config"]
    assert updated_cfg["idle_timeout_seconds"] == 90.0
    assert updated_cfg["keep_alive_interval_seconds"] == 20.0
