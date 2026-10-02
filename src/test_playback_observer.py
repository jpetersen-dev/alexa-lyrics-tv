"""
Suite de pruebas de validación para la Fase 1:
Observador de reproducción de Spotify controlado mediante Alexa.
"""

import sys
import os
import time
import json
from typing import Optional

# Asegurar importación de src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.spotify_provider import SpotifyPlaybackProvider
from src.models import PlaybackState


def run_single_check():
    """Realiza una única consulta y muestra el estado actual."""
    provider = SpotifyPlaybackProvider()

    if not provider.is_authenticated():
        print("❌ Error: El proveedor no está autenticado.")
        print("Ejecuta primero: python src/oauth_server.py y autoriza la cuenta de Camila.")
        return False

    print("\n🔍 Consultando endpoint /v1/me/player...")
    t_start = time.time()
    state = provider.get_current_playback()
    latency_ms = (time.time() - t_start) * 1000

    print(f"⏱️ Tiempo de respuesta HTTP (latencia de consulta): {latency_ms:.1f} ms")

    if state is None:
        print("ℹ️ Resultado: No hay reproducción activa en este momento (HTTP 204 No Content).")
        print("Asegúrate de que Alexa esté reproduciendo música desde la cuenta de Camila.")
        return True

    print("\n✅ Datos obtenidos exitosamente de Spotify:")
    print(f"   • Título:         {state.title}")
    print(f"   • Artista:        {state.artist}")
    print(f"   • Álbum:          {state.album or 'N/A'}")
    print(f"   • Duración:       {state.duration_ms} ms ({state.duration_seconds:.1f}s)")
    print(f"   • Progreso:       {state.progress_ms} ms ({state.progress_seconds:.1f}s)")
    print(f"   • Estado:         {'▶ PLAYING' if state.is_playing else '⏸ PAUSED'}")
    print(f"   • Dispositivo:    {state.device_name} ({state.device_type}) [ID: {state.device_id}]")
    print(f"   • Server Time:    {state.timestamp_ms}")
    print(f"   • Local Obs Time: {state.observed_at}")
    return True


def run_live_monitor(interval_seconds: float = 1.0, max_duration: int = 120):
    """
    Monitor continuo en tiempo real para observar cambios de canción, pausas y reanudaciones.
    Ideal para ejecutar las pruebas B, C, D y E mientras se dan órdenes de voz a Alexa.
    """
    provider = SpotifyPlaybackProvider()

    if not provider.is_authenticated():
        print("❌ Error: No autenticado.")
        return

    print("=" * 70)
    print("🎙️ ALEXA LYRICS TV — MONITOR DE REPRODUCCIÓN EN VIVO (FASE 1)")
    print(f"Intervalo de polling: {interval_seconds}s | Duración máx: {max_duration}s")
    print("Prueba dar órdenes a Alexa: 'pausa', 'continúa', 'siguiente canción'...")
    print("Presiona Ctrl+C para salir.")
    print("=" * 70)

    last_track_id = None
    last_is_playing = None
    last_progress = 0
    last_query_time = 0

    start_time = time.time()
    iteration = 0

    try:
        while time.time() - start_time < max_duration:
            iteration += 1
            t_req_start = time.time()
            state = provider.get_current_playback()
            latency_ms = (time.time() - t_req_start) * 1000

            now_str = time.strftime("%H:%M:%S")

            if state is None:
                print(f"[{now_str}] ⚪ Sin reproducción activa (204 No Content) [lat: {latency_ms:.0f}ms]")
                last_track_id = None
                last_is_playing = None
            else:
                # Detectar evento de cambio de canción
                if state.track_id != last_track_id:
                    print(f"\n🎵 [{now_str}] CAMBIO DE CANCIÓN DETECTADO:")
                    print(f"   ► Canción:  {state.artist} - '{state.title}'")
                    print(f"   ► Álbum:    {state.album}")
                    print(f"   ► Duración: {state.duration_seconds:.1f}s")
                    print(f"   ► Dispositivo: {state.device_name} ({state.device_type})\n")
                    last_track_id = state.track_id

                # Detectar evento de pausa/reanudación
                if last_is_playing is not None and state.is_playing != last_is_playing:
                    event_type = "▶ REANUDACIÓN" if state.is_playing else "⏸ PAUSA"
                    print(f"\n⚡ [{now_str}] EVENTO DE TRANSPORTE: {event_type} en pos {state.progress_seconds:.1f}s\n")

                last_is_playing = state.is_playing

                # Imprimir línea de telemetría continua
                status_icon = "▶" if state.is_playing else "⏸"
                pos_str = f"{state.progress_seconds:5.1f}s / {state.duration_seconds:5.1f}s"
                print(
                    f"[{now_str}] {status_icon} [{pos_str}] '{state.title[:25]:<25}' "
                    f"dev:{state.device_name or 'N/A':<12} lat:{latency_ms:4.0f}ms"
                )

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\nMonitor detenido por el usuario.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        run_single_check()
    else:
        run_live_monitor()
