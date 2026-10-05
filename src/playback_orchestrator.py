"""
Orquestador de Reproducción y Ciclo de Vida Automático (Playback Orchestrator).
Gestiona el cambio entre fuentes de audio (Mock, Webhook, Spotify, Home Assistant),
la consulta periódica del estado de reproducción, y el ciclo de vida automático
de Google Cast (auto-lanzamiento en TV al reproducir y auto-cierre tras inactividad).
"""

import time
import logging
from typing import Dict, Any, Optional, List

from .models import PlaybackState
from .provider_base import PlaybackProvider
from .mock_provider import MockPlaybackProvider
from .webhook_provider import WebhookPlaybackProvider
from .hass_provider import HomeAssistantPlaybackProvider
from .spotify_provider import SpotifyPlaybackProvider
from .sync_engine import SyncEngine
from .cast_controller import CastManager, DEFAULT_CAST_APP_ID
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class PlaybackOrchestrator:
    """
    Coordina la fuente de audio activa y el ciclo de vida del televisor.
    """

    def __init__(
        self,
        engine: SyncEngine,
        cast_manager: CastManager,
        initial_provider: str = "mock",
        config_manager: Optional[ConfigManager] = None,
    ):
        self.engine = engine
        self.cast_manager = cast_manager
        self.config_manager = config_manager

        # Instanciar proveedores disponibles
        self.mock_provider = MockPlaybackProvider()
        self.webhook_provider = WebhookPlaybackProvider()
        self.hass_provider = HomeAssistantPlaybackProvider()
        self.spotify_provider = SpotifyPlaybackProvider()

        self.providers: Dict[str, PlaybackProvider] = {
            "mock": self.mock_provider,
            "webhook": self.webhook_provider,
            "homeassistant": self.hass_provider,
            "spotify": self.spotify_provider,
        }

        # Cargar parámetros desde ConfigManager o valores predeterminados
        if self.config_manager:
            self.active_provider_name = self.config_manager.get("default_provider", initial_provider)
            self.auto_cast_enabled: bool = bool(self.config_manager.get("autocast_enabled", False))
            self.target_cast_device: Optional[str] = self.config_manager.get("target_cast_device", None)
            self.target_cast_host: Optional[str] = self.config_manager.get("target_cast_host", None)
            self.target_cast_app_id: str = self.config_manager.get("target_cast_app_id", DEFAULT_CAST_APP_ID)
            self.idle_timeout_seconds: float = float(self.config_manager.get("idle_timeout_seconds", 180.0))
            self.keep_alive_interval_seconds: float = float(
                self.config_manager.get("keep_alive_interval_seconds", 15.0)
            )

            # Configuración opcional de Home Assistant desde config persistente
            h_url = self.config_manager.get("hass_url")
            h_token = self.config_manager.get("hass_token")
            h_entity = self.config_manager.get("hass_alexa_entity")
            if h_url:
                self.hass_provider.base_url = h_url.rstrip("/")
            if h_token:
                self.hass_provider.access_token = h_token
            if h_entity:
                self.hass_provider.entity_id = h_entity
        else:
            self.active_provider_name = initial_provider
            self.auto_cast_enabled = False
            self.target_cast_device = None
            self.target_cast_host = None
            self.target_cast_app_id = DEFAULT_CAST_APP_ID
            self.idle_timeout_seconds = 180.0
            self.keep_alive_interval_seconds = 15.0

        # Seguimiento temporal del ciclo de vida
        self._last_playing_time: float = time.time()
        self._last_keep_alive_time: float = 0.0
        self._was_playing: bool = False

    @property
    def current_provider(self) -> PlaybackProvider:
        return self.providers.get(self.active_provider_name, self.mock_provider)

    def set_active_provider(self, name: str) -> bool:
        """Cambia el proveedor de reproducción activo."""
        if name in self.providers:
            self.active_provider_name = name
            if self.config_manager:
                self.config_manager.set("default_provider", name)
                self.config_manager.save()
            logger.info(f"[Orchestrator] Proveedor activo cambiado a: {name}")
            return True
        return False

    def get_providers_status(self) -> Dict[str, Any]:
        """Reporta el estado de autenticación y disponibilidad de cada proveedor."""
        return {
            "active_provider": self.active_provider_name,
            "providers": {
                name: {
                    "authenticated": p.is_authenticated(),
                    "type": p.__class__.__name__,
                }
                for name, p in self.providers.items()
            },
            "autocast": {
                "enabled": self.auto_cast_enabled,
                "target_device": self.target_cast_device,
                "target_host": self.target_cast_host,
                "target_app_id": self.target_cast_app_id,
                "idle_timeout_seconds": self.idle_timeout_seconds,
            },
        }

    def configure_autocast(
        self,
        enabled: Optional[bool] = None,
        target_device: Optional[str] = None,
        target_host: Optional[str] = None,
        target_app_id: Optional[str] = None,
        idle_timeout_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Configura el comportamiento automático de Google Cast."""
        if enabled is not None:
            self.auto_cast_enabled = enabled
            if self.config_manager:
                self.config_manager.set("autocast_enabled", enabled)
        if target_device is not None:
            self.target_cast_device = target_device
            if self.config_manager:
                self.config_manager.set("target_cast_device", target_device)
        if target_host is not None:
            self.target_cast_host = target_host
            if self.config_manager:
                self.config_manager.set("target_cast_host", target_host)
        if target_app_id is not None:
            self.target_cast_app_id = target_app_id
            if self.config_manager:
                self.config_manager.set("target_cast_app_id", target_app_id)
        if idle_timeout_seconds is not None:
            self.idle_timeout_seconds = idle_timeout_seconds
            if self.config_manager:
                self.config_manager.set("idle_timeout_seconds", idle_timeout_seconds)

        if self.config_manager:
            self.config_manager.save()

        logger.info(
            f"[Orchestrator] AutoCast configurado: enabled={self.auto_cast_enabled}, "
            f"target={self.target_cast_device or self.target_cast_host}"
        )
        return self.get_providers_status()["autocast"]

    def tick(self) -> Optional[Any]:
        """
        Ejecuta un ciclo de observación, actualización de estado del SyncEngine
        y evaluación de las reglas de auto-lanzamiento / auto-cierre de TV.
        """
        provider = self.current_provider
        try:
            playback = provider.get_current_playback()
        except Exception as e:
            logger.error(f"[Orchestrator] Error obteniendo playback de {self.active_provider_name}: {e}")
            playback = None

        # Procesar observación en el motor de sincronización
        synced_state = self.engine.process_observation(playback)

        now = time.time()
        is_playing = synced_state.is_playing if synced_state else False

        # --- Enviar PING Keep-Alive a Chromecast si está conectado ---
        if self.cast_manager.is_connected:
            if (now - self._last_keep_alive_time) >= self.keep_alive_interval_seconds:
                self.cast_manager.send_keep_alive()
                self._last_keep_alive_time = now

        # --- Gestión Automática del Ciclo de Vida de Chromecast ---
        if is_playing:
            self._last_playing_time = now

            # 1. Detección de inicio de reproducción -> Auto-lanzar en TV
            if not self._was_playing and self.auto_cast_enabled:
                if not self.cast_manager.is_connected:
                    logger.info("[Orchestrator] Inicio de reproducción detectado. Conectando a Chromecast...")
                    connected = self.cast_manager.connect_to_device(
                        name=self.target_cast_device,
                        host=self.target_cast_host,
                    )
                    if connected:
                        logger.info(f"[Orchestrator] Lanzando app {self.target_cast_app_id} en TV...")
                        self.cast_manager.launch_app(self.target_cast_app_id)
                        self.cast_manager.send_playback_state(synced_state.to_dict())

            self._was_playing = True

        else:
            # 2. Detección de pausa o detención
            if self._was_playing:
                self._was_playing = False
                logger.info("[Orchestrator] Reproducción detenida o pausada.")

            # 3. Inactividad prolongada -> Auto-cerrar Cast para liberar el TV
            if (
                self.auto_cast_enabled
                and self.cast_manager.is_connected
                and (now - self._last_playing_time) > self.idle_timeout_seconds
            ):
                logger.info(
                    f"[Orchestrator] Inactividad superó {self.idle_timeout_seconds}s. "
                    "Cerrando sesión de Cast en la TV..."
                )
                self.cast_manager.quit_app()
                self.cast_manager.disconnect()

        return synced_state
