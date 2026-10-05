"""
Servidor de transporte en tiempo real con FastAPI y WebSockets.
Integra el SyncEngine en un bucle asíncrono y expone el estado de reproducción
hacia el visor web (React/Vite) y el futuro receptor de Google Cast.
"""

import sys
import os
import asyncio
import time
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

# Compatibilidad de rutas y consola UTF-8 en Windows
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.mock_provider import MockPlaybackProvider
from src.lrclib_provider import LRCLIBLyricsProvider
from src.sync_engine import SyncEngine
from src.sync_models import SyncedPlaybackState
from src.cast_controller import CastManager, DEFAULT_CAST_APP_ID
from src.playback_orchestrator import PlaybackOrchestrator
from src.config_manager import ConfigManager


# --- Modelos de Entrada para la API Mock, Cast, Proveedores y AutoCast ---
class SeekRequest(BaseModel):
    position_ms: int


class LoadTrackRequest(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: int = 240000
    start_position_ms: int = 0
    is_playing: bool = True


class CastConnectRequest(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    timeout: float = 5.0


class CastLaunchRequest(BaseModel):
    app_id: str = DEFAULT_CAST_APP_ID


class SetProviderRequest(BaseModel):
    provider: str


class WebhookPlaybackRequest(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: int = 0
    progress_ms: int = 0
    is_playing: bool = True
    device_name: Optional[str] = "Alexa Echo"


class AutoCastConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    target_device: Optional[str] = None
    target_host: Optional[str] = None
    target_app_id: Optional[str] = None
    idle_timeout_seconds: Optional[float] = None


class AppConfigRequest(BaseModel):
    default_provider: Optional[str] = None
    autocast_enabled: Optional[bool] = None
    target_cast_device: Optional[str] = None
    target_cast_host: Optional[str] = None
    target_cast_app_id: Optional[str] = None
    idle_timeout_seconds: Optional[float] = None
    keep_alive_interval_seconds: Optional[float] = None
    hass_url: Optional[str] = None
    hass_token: Optional[str] = None
    hass_alexa_entity: Optional[str] = None



# --- Gestor de Conexiones WebSocket y Cast ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: Dict[str, Any]):
        if not self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


# --- Estado Global de la Aplicación ---
manager = ConnectionManager()
config_manager = ConfigManager()
lyrics_provider = LRCLIBLyricsProvider()
engine = SyncEngine(lyrics_provider=lyrics_provider)
cast_manager = CastManager()
orchestrator = PlaybackOrchestrator(
    engine=engine,
    cast_manager=cast_manager,
    config_manager=config_manager,
)
mock_provider = orchestrator.mock_provider

# Inicializar con Queen - Bohemian Rhapsody
mock_provider.load_track(
    track_id="queen_bohemian_rhapsody",
    title="Bohemian Rhapsody",
    artist="Queen",
    album="A Night at the Opera",
    duration_ms=354320,
    start_position_ms=0,
    is_playing=True,
)


# --- Bucle de Sincronización en Segundo Plano ---
async def background_sync_loop():
    """
    Bucle asíncrono que consulta el PlaybackOrchestrator cada 150 ms y emite
    actualizaciones ante cambios de línea, pausas, saltos o pulsos de referencia (3s).
    Transmite simultáneamente hacia WebSockets (navegador/móvil) y Google Cast (TV).
    """
    last_line_idx = -2
    last_is_playing = None
    last_track = None
    last_pulse_time = 0.0

    while True:
        try:
            state = orchestrator.tick()

            if state:
                now = time.time()
                line_changed = state.active_line_index != last_line_idx
                state_changed = state.is_playing != last_is_playing
                track_changed = state.track != last_track
                pulse_due = (now - last_pulse_time) >= 3.0  # Pulso cada 3s para recalibrar

                if line_changed or state_changed or track_changed or pulse_due:
                    payload = state.to_dict()
                    # 1. Enviar a clientes WebSocket
                    await manager.broadcast(payload)

                    # 2. Enviar a Google Cast si hay un televisor conectado
                    if cast_manager.is_connected:
                        cast_manager.send_playback_state(payload)

                    last_line_idx = state.active_line_index
                    last_is_playing = state.is_playing
                    last_track = state.track
                    last_pulse_time = now

        except Exception as e:
            print(f"[Server] Error en background_sync_loop: {e}")

        await asyncio.sleep(0.15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar bucle en segundo plano al arrancar
    sync_task = asyncio.create_task(background_sync_loop())
    print("🚀 Servidor FastAPI + SyncEngine + Cast iniciado correctamente.")
    yield
    # Desconectar Cast y cancelar tarea al detener
    cast_manager.disconnect()
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass


# --- Aplicación FastAPI ---
app = FastAPI(
    title="Alexa Lyrics TV — Sync Transport Server",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS para permitir peticiones desde el servidor Vite de desarrollo (puertos 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoint WebSocket ---
@app.websocket("/ws/playback")
async def websocket_playback(websocket: WebSocket):
    await manager.connect(websocket)
    # Enviar estado actual inmediatamente al conectar
    latest_state = engine.last_state
    if latest_state:
        await websocket.send_json(latest_state.to_dict())

    try:
        while True:
            # Mantener conexión abierta y responder a posibles pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# --- Endpoints REST Auxiliares para Control de Simulación (Mock) ---
@app.get("/api/status")
async def get_status():
    latest = engine.last_state
    return {
        "status": "online",
        "active_clients": len(manager.active_connections),
        "playback": latest.to_dict() if latest else None,
    }


@app.post("/api/mock/play")
async def mock_play(start_ms: int = 0):
    mock_provider.play(start_position_ms=start_ms)
    state = engine.process_observation(mock_provider.get_current_playback())
    await manager.broadcast(state.to_dict())
    return {"message": "Reproducción iniciada", "state": state.to_dict()}


@app.post("/api/mock/pause")
async def mock_pause():
    mock_provider.pause()
    state = engine.process_observation(mock_provider.get_current_playback())
    await manager.broadcast(state.to_dict())
    return {"message": "Pausado", "state": state.to_dict()}


@app.post("/api/mock/resume")
async def mock_resume():
    mock_provider.resume()
    state = engine.process_observation(mock_provider.get_current_playback())
    await manager.broadcast(state.to_dict())
    return {"message": "Reanudado", "state": state.to_dict()}


@app.post("/api/mock/seek")
async def mock_seek(req: SeekRequest):
    mock_provider.seek(req.position_ms)
    state = engine.process_observation(mock_provider.get_current_playback())
    await manager.broadcast(state.to_dict())
    return {"message": f"Seek a {req.position_ms} ms", "state": state.to_dict()}


@app.post("/api/mock/next")
async def mock_next():
    mock_provider.next_track()
    state = engine.process_observation(mock_provider.get_current_playback())
    await manager.broadcast(state.to_dict())
    return {"message": "Siguiente pista", "state": state.to_dict()}


@app.post("/api/mock/load")
async def mock_load_track(req: LoadTrackRequest):
    mock_provider.load_track(
        track_id=f"custom_{int(time.time())}",
        title=req.title,
        artist=req.artist,
        album=req.album,
        duration_ms=req.duration_ms,
        start_position_ms=req.start_position_ms,
        is_playing=req.is_playing,
    )
    state = engine.process_observation(mock_provider.get_current_playback())
    await manager.broadcast(state.to_dict())
    return {"message": f"Pista cargada: {req.artist} - {req.title}", "state": state.to_dict()}


# --- Endpoints REST para Gestión de Google Cast ---
@app.get("/api/cast/status")
async def get_cast_status():
    device_name = (
        cast_manager.cast_device.name
        if (cast_manager.is_connected and cast_manager.cast_device)
        else None
    )
    model_name = (
        cast_manager.cast_device.model_name
        if (cast_manager.is_connected and cast_manager.cast_device)
        else None
    )
    return {
        "connected": cast_manager.is_connected,
        "device_name": device_name,
        "model_name": model_name,
    }


@app.get("/api/cast/devices")
async def get_cast_devices(timeout: float = 4.0, host: Optional[str] = None):
    devices = cast_manager.discover_devices(timeout=timeout, host=host)
    return {"devices": devices}


@app.post("/api/cast/connect")
async def connect_cast(req: CastConnectRequest):
    success = cast_manager.connect_to_device(name=req.name, host=req.host, timeout=req.timeout)
    if not success:
        raise HTTPException(status_code=400, detail="No se pudo conectar al dispositivo Chromecast")
    device_name = cast_manager.cast_device.name if cast_manager.cast_device else "Desconocido"
    return {
        "message": f"Conectado a Chromecast: {device_name}",
        "device": device_name,
    }


@app.post("/api/cast/launch")
async def launch_cast_app(req: CastLaunchRequest):
    if not cast_manager.is_connected:
        raise HTTPException(status_code=400, detail="No hay ningún dispositivo Chromecast conectado")
    success = cast_manager.launch_app(req.app_id)
    if not success:
        raise HTTPException(status_code=500, detail=f"No se pudo iniciar la aplicación {req.app_id}")
    # Enviar estado actual de inmediato
    if engine.last_state:
        cast_manager.send_playback_state(engine.last_state.to_dict())
    return {"message": f"Aplicación {req.app_id} lanzada exitosamente"}


@app.post("/api/cast/disconnect")
async def disconnect_cast():
    cast_manager.disconnect()
    return {"message": "Desconectado de Chromecast"}


# --- Endpoints REST para Gestión de Proveedores de Reproducción y AutoCast ---
@app.get("/api/playback/provider")
async def get_playback_provider():
    return orchestrator.get_providers_status()


@app.post("/api/playback/provider")
async def set_playback_provider(req: SetProviderRequest):
    success = orchestrator.set_active_provider(req.provider)
    if not success:
        raise HTTPException(status_code=400, detail=f"Proveedor desconocido: {req.provider}")
    return {"message": f"Proveedor activo: {req.provider}", "status": orchestrator.get_providers_status()}


@app.post("/api/playback/update")
async def update_playback_webhook(req: WebhookPlaybackRequest):
    orchestrator.webhook_provider.update_playback(
        title=req.title,
        artist=req.artist,
        album=req.album,
        duration_ms=req.duration_ms,
        progress_ms=req.progress_ms,
        is_playing=req.is_playing,
        device_name=req.device_name,
    )
    if orchestrator.active_provider_name != "webhook":
        orchestrator.set_active_provider("webhook")

    state = orchestrator.tick()
    if state:
        await manager.broadcast(state.to_dict())
        if cast_manager.is_connected:
            cast_manager.send_playback_state(state.to_dict())
    return {"message": "Estado de reproducción actualizado", "state": state.to_dict() if state else None}


# --- Endpoints de Autenticación y Control de Spotify Connect ---
@app.get("/api/spotify/login")
async def spotify_login():
    """Genera la URL de autorización oficial de Spotify y redirige al usuario."""
    spotify_p = orchestrator.spotify_provider
    if not spotify_p.client_id or not spotify_p.client_secret:
        raise HTTPException(
            status_code=400,
            detail="Faltan credenciales de Spotify. Configura SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET en tu archivo .env",
        )
    auth_url = spotify_p.get_authorization_url()
    return RedirectResponse(url=auth_url)


@app.get("/api/spotify/callback")
async def spotify_callback(code: Optional[str] = None, error: Optional[str] = None):
    """Callback de OAuth 2.0 donde Spotify retorna el código de autorización."""
    if error or not code:
        raise HTTPException(status_code=400, detail=f"Error en autorización de Spotify: {error or 'Código no recibido'}")

    spotify_p = orchestrator.spotify_provider
    try:
        spotify_p.exchange_code_for_tokens(code)
        orchestrator.set_active_provider("spotify")
        return RedirectResponse(url="/?spotify=connected")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error intercambiando código de Spotify: {e}")


@app.get("/api/spotify/status")
async def spotify_status():
    spotify_p = orchestrator.spotify_provider
    return {
        "configured": bool(spotify_p.client_id and spotify_p.client_secret),
        "authenticated": spotify_p.is_authenticated(),
        "client_id": (spotify_p.client_id[:6] + "...") if spotify_p.client_id else None,
        "is_active_provider": orchestrator.active_provider_name == "spotify",
    }


@app.post("/api/spotify/disconnect")
async def spotify_disconnect():
    spotify_p = orchestrator.spotify_provider
    spotify_p.tokens = {}
    if os.path.exists(spotify_p.tokens_file):
        try:
            os.remove(spotify_p.tokens_file)
        except Exception:
            pass
    if orchestrator.active_provider_name == "spotify":
        orchestrator.set_active_provider("mock")
    return {"message": "Sesión de Spotify desconectada"}


@app.get("/api/autocast/config")
async def get_autocast_config():
    return orchestrator.get_providers_status()["autocast"]


@app.post("/api/autocast/config")
async def configure_autocast(req: AutoCastConfigRequest):
    cfg = orchestrator.configure_autocast(
        enabled=req.enabled,
        target_device=req.target_device,
        target_host=req.target_host,
        target_app_id=req.target_app_id,
        idle_timeout_seconds=req.idle_timeout_seconds,
    )
    return {"message": "Configuración de AutoCast actualizada", "autocast": cfg}


@app.get("/api/config")
async def get_config():
    return config_manager.to_dict()


@app.post("/api/config")
async def update_config(req: AppConfigRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    config_manager.update(updates)
    config_manager.save()
    # Aplicar cambios al orquestador en caliente
    if req.default_provider:
        orchestrator.set_active_provider(req.default_provider)
    orchestrator.configure_autocast(
        enabled=req.autocast_enabled,
        target_device=req.target_cast_device,
        target_host=req.target_cast_host,
        target_app_id=req.target_cast_app_id,
        idle_timeout_seconds=req.idle_timeout_seconds,
    )
    if req.keep_alive_interval_seconds is not None:
        orchestrator.keep_alive_interval_seconds = req.keep_alive_interval_seconds
    if req.hass_url:
        orchestrator.hass_provider.base_url = req.hass_url.rstrip("/")
    if req.hass_token:
        orchestrator.hass_provider.access_token = req.hass_token
    if req.hass_alexa_entity:
        orchestrator.hass_provider.entity_id = req.hass_alexa_entity
    return {"message": "Configuración global actualizada", "config": config_manager.to_dict()}



# --- Montaje de Archivos Estáticos de Frontend (para producción/dist) ---
web_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")
if os.path.exists(web_dist):
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="static_web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)
