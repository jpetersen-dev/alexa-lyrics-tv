"""
Gestor de configuración persistente para Alexa Lyrics TV.
Almacena y recupera preferencias del usuario (dispositivo Chromecast, proveedor activo,
tiempos de inactividad, flags de AutoCast) en un archivo JSON local ('config.json').
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"
)

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_provider": "mock",
    "autocast_enabled": False,
    "target_cast_device": None,
    "target_cast_host": None,
    "target_cast_app_id": "CC1AD845",
    "idle_timeout_seconds": 180.0,
    "keep_alive_interval_seconds": 15.0,
    "hass_url": "http://homeassistant.local:8123",
    "hass_token": "",
    "hass_alexa_entity": "media_player.echo_dot",
}


class ConfigManager:
    """
    Lee y escribe la configuración persistente en formato JSON.
    """

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._config: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Carga la configuración desde el disco o genera una predeterminada."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(data)
                    return cfg
            except Exception as e:
                logger.error(f"Error leyendo {self.config_path}, usando valores por defecto: {e}")
        return DEFAULT_CONFIG.copy()

    def save(self) -> bool:
        """Guarda la configuración actual en el disco."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error guardando {self.config_path}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def update(self, values: Dict[str, Any]) -> None:
        self._config.update(values)

    def to_dict(self) -> Dict[str, Any]:
        return self._config.copy()
