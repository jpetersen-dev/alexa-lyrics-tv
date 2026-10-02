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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.mock_provider import MockPlaybackProvider
from src.lrclib_provider import LRCLIBLyricsProvider
from src.sync_engine import SyncEngine
from src.sync_models import SyncedPlaybackState


# --- Modelos de Entrada para la API Mock ---
class SeekRequest(BaseModel):
    position_ms: int


class LoadTrackRequest(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: int = 240000
    start_position_ms: int = 0
    is_playing: bool = True


# --- Gestor de Conexiones WebSocket ---
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
mock_provider = MockPlaybackProvider()
lyrics_provider = LRCLIBLyricsProvider()
engine = SyncEngine(lyrics_provider=lyrics_provider)

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
    Bucle asíncrono que consulta el PlaybackProvider cada 200 ms y emite
    actualizaciones ante cambios de línea, pausas, saltos o pulsos de referencia (3s).
    """
    last_line_idx = -2
    last_is_playing = None
    last_track = None
    last_pulse_time = 0.0

    while True:
        try:
            playback = mock_provider.get_current_playback()
            state = engine.process_observation(playback)

            now = time.time()
            line_changed = state.active_line_index != last_line_idx
            state_changed = state.is_playing != last_is_playing
            track_changed = state.track != last_track
            pulse_due = (now - last_pulse_time) >= 3.0  # Pulso cada 3s para recalibrar

            if line_changed or state_changed or track_changed or pulse_due:
                payload = state.to_dict()
                await manager.broadcast(payload)

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
    print("🚀 Servidor FastAPI + SyncEngine iniciado correctamente.")
    yield
    # Cancelar tarea al detener
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


# --- Montaje de Archivos Estáticos de Frontend (para producción/dist) ---
web_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")
if os.path.exists(web_dist):
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="static_web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8000, reload=True)
