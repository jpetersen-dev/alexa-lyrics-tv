"""
Controlador de Google Cast para Alexa Lyrics TV.
Gestiona el descubrimiento de dispositivos Chromecast en la red local (mDNS),
la conexión mediante TLS/socket 8009, el lanzamiento del Custom Web Receiver
y la transmisión de estados de sincronización (SyncedPlaybackState) a través
del namespace dedicado 'urn:x-cast:com.alexalyricstv.sync'.
"""

import json
import logging
import threading
import time
from typing import Dict, Any, List, Optional

import pychromecast
from pychromecast.controllers import BaseController

logger = logging.getLogger(__name__)

# Namespace registrado para la comunicación bidireccional Cast <-> Daemon
CAST_NAMESPACE = "urn:x-cast:com.alexalyricstv.sync"

# App ID por defecto o en desarrollo (configurable vía variable de entorno o consola)
# Ejemplo: 'CC1AD845' es el Default Media Receiver; los Custom Web Receivers usan su propio ID (8 hex).
DEFAULT_CAST_APP_ID = "CC1AD845"


class LyricsCastController(BaseController):
    """
    Canal de mensajes personalizado (Custom Channel) sobre el protocolo Cast.
    Permite enviar payloads de texto/JSON hacia el Custom Web Receiver.
    """

    def __init__(self, namespace: str = CAST_NAMESPACE):
        super().__init__(namespace, target_platform=False)
        self.last_received_message: Optional[Dict[str, Any]] = None

    def receive_message(self, message: str, data: Dict[str, Any]) -> bool:
        """Procesa mensajes entrantes desde el Custom Web Receiver en la TV."""
        try:
            logger.info(f"Mensaje recibido desde Cast Receiver: {data}")
            self.last_received_message = data
            return True
        except Exception as e:
            logger.error(f"Error procesando mensaje desde Cast: {e}")
            return False

    def send_synced_state(self, state_dict: Dict[str, Any]) -> None:
        """Transmite el estado de reproducción actual al Custom Web Receiver."""
        try:
            payload = json.dumps(state_dict)
            self.send_message(payload)
            logger.debug(f"Estado enviado al Cast Receiver ({len(payload)} bytes)")
        except Exception as e:
            logger.error(f"Error enviando estado al Cast Receiver: {e}")


class CastManager:
    """
    Administrador del ciclo de vida de la conexión Cast.
    Soporta descubrimiento automático (mDNS zeroconf) y conexión directa por IP.
    """

    def __init__(self, namespace: str = CAST_NAMESPACE):
        self.namespace = namespace
        self.cast_device: Optional[pychromecast.Chromecast] = None
        self.cast_controller: Optional[LyricsCastController] = None
        self.browser: Optional[Any] = None
        self._is_connected = False
        self._lock = threading.Lock()
        self._device_cache: Dict[str, str] = {}  # name.lower() -> host
        self._last_connected_host: Optional[str] = None
        self._last_connected_name: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.cast_device is not None

    def discover_devices(self, timeout: float = 5.0, host: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Escanea la red local en busca de dispositivos Chromecast o se conecta a una IP específica.
        Actualiza la caché de dispositivos conocidos para conexiones instantáneas.
        """
        devices = []
        if host:
            try:
                cast = pychromecast.Chromecast(host)
                dev_info = {
                    "name": cast.name,
                    "model": cast.model_name,
                    "host": host,
                    "port": cast.port,
                    "uuid": str(cast.uuid),
                }
                devices.append(dev_info)
                self._device_cache[cast.name.lower()] = host
                cast.disconnect()
                return devices
            except Exception as e:
                logger.warning(f"No se pudo conectar al host {host}: {e}")
                return []

        try:
            chromecasts, browser = pychromecast.get_chromecasts(timeout=timeout)
            self.browser = browser
            for cc in chromecasts:
                chost = getattr(cc.cast_info, "host", "unknown")
                devices.append({
                    "name": cc.name,
                    "model": cc.model_name,
                    "host": chost,
                    "port": getattr(cc.cast_info, "port", 8009),
                    "uuid": str(cc.uuid),
                })
                if chost != "unknown":
                    self._device_cache[cc.name.lower()] = chost
            pychromecast.stop_discovery(browser)
        except Exception as e:
            logger.error(f"Error durante el descubrimiento de Cast: {e}")

        return devices

    def connect_to_device(
        self,
        name: Optional[str] = None,
        host: Optional[str] = None,
        timeout: float = 5.0,
    ) -> bool:
        """
        Establece conexión física TLS con un Chromecast (por nombre o IP).
        Usa la caché de IP si el dispositivo ya fue descubierto previamente para evitar latencia mDNS.
        """
        with self._lock:
            self.disconnect()

            # Optimización: si se especifica nombre pero tenemos la IP en caché, conectar directamente
            target_host = host
            if not target_host and name and name.lower() in self._device_cache:
                cached_host = self._device_cache[name.lower()]
                logger.info(f"Usando host en caché ({cached_host}) para Chromecast '{name}'...")
                target_host = cached_host

            try:
                if target_host:
                    logger.info(f"Conectando a Chromecast por IP: {target_host}...")
                    self.cast_device = pychromecast.Chromecast(target_host)
                else:
                    logger.info(f"Buscando Chromecast con nombre '{name}' vía mDNS...")
                    chromecasts, browser = pychromecast.get_chromecasts(timeout=timeout)
                    target = None
                    for cc in chromecasts:
                        if name is None or cc.name.lower() == name.lower():
                            target = cc
                            break
                    pychromecast.stop_discovery(browser)

                    if not target:
                        logger.warning(f"No se encontró ningún Chromecast compatible con '{name}'")
                        return False
                    self.cast_device = target

                # Esperar a que el socket y la sesión estén listos
                self.cast_device.wait()

                # Instanciar y registrar el canal personalizado
                self.cast_controller = LyricsCastController(self.namespace)
                self.cast_device.register_handler(self.cast_controller)

                self._is_connected = True
                self._last_connected_name = self.cast_device.name
                self._last_connected_host = getattr(self.cast_device.cast_info, "host", target_host)
                if self.cast_device.name and self._last_connected_host:
                    self._device_cache[self.cast_device.name.lower()] = self._last_connected_host

                logger.info(
                    f"Conectado exitosamente a Chromecast: {self.cast_device.name} "
                    f"({self.cast_device.model_name})"
                )
                return True

            except Exception as e:
                logger.error(f"Error conectando a Chromecast: {e}")
                self.disconnect()
                return False

    def send_keep_alive(self) -> bool:
        """Envía un mensaje PING ligero por el Custom Channel para evitar caídas de socket."""
        if not self.is_connected or not self.cast_controller:
            return False
        try:
            self.cast_controller.send_message(json.dumps({"type": "PING", "time": time.time()}))
            return True
        except Exception as e:
            logger.warning(f"Error enviando keep-alive al Chromecast (posible desconexión): {e}")
            self.disconnect()
            return False

    def launch_app(self, app_id: str = DEFAULT_CAST_APP_ID, timeout: float = 10.0) -> bool:
        """
        Lanza la aplicación web receiver en el Chromecast según su Application ID.
        """
        if not self.is_connected or not self.cast_device:
            logger.warning("No hay Chromecast conectado para lanzar la aplicación.")
            return False

        try:
            logger.info(f"Lanzando aplicación Cast ID: {app_id}...")
            self.cast_device.start_app(app_id)
            
            # Dar tiempo a que el receiver inicialice el socket TLS
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.cast_device.app_id == app_id:
                    logger.info(f"Aplicación {app_id} activa en Chromecast.")
                    return True
                time.sleep(0.5)

            logger.warning(f"Timeout esperando activación de {app_id} (App actual: {self.cast_device.app_id})")
            return self.cast_device.app_id == app_id
        except Exception as e:
            logger.error(f"Error lanzando aplicación Cast: {e}")
            self.disconnect()
            return False

    def send_playback_state(self, state_dict: Dict[str, Any]) -> bool:
        """Envía el estado de sincronización al Custom Web Receiver."""
        if not self.is_connected or not self.cast_controller:
            return False

        try:
            self.cast_controller.send_synced_state(state_dict)
            return True
        except Exception as e:
            logger.warning(f"Error transmitiendo estado al Cast (cerrando conexión): {e}")
            self.disconnect()
            return False

    def quit_app(self) -> None:
        """Cierra la aplicación activa en el televisor volviendo al backdrop."""
        if self.is_connected and self.cast_device:
            try:
                logger.info("Cerrando aplicación en Chromecast...")
                self.cast_device.quit_app()
            except Exception as e:
                logger.error(f"Error cerrando app en Chromecast: {e}")

    def disconnect(self) -> None:
        """Libera la conexión física y los manejadores de eventos."""
        if self.cast_device:
            try:
                self.cast_device.disconnect()
            except Exception:
                pass
            self.cast_device = None
            self.cast_controller = None
        self._is_connected = False
