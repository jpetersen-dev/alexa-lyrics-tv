"""
Herramienta de diagnóstico instrumental por consola (CLI).
Permite visualizar la sincronización en tiempo real del SyncEngine:
progreso, estado de transporte, verso activo y próximos versos.
"""

import sys
import os
import time

# Asegurar importación de src y compatibilidad UTF-8 en Windows
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.mock_provider import MockPlaybackProvider
from src.lrclib_provider import LRCLIBLyricsProvider
from src.sync_engine import SyncEngine
from src.sync_models import PlaybackEventType


def render_display(state, event_msg: str = ""):
    """Renderiza el estado actual en la terminal."""
    os.system("cls" if sys.platform == "win32" else "clear")

    status_icon = "▶ REPRODUCIENDO" if state.is_playing else "⏸ EN PAUSA"
    pos_s = state.position_ms / 1000.0
    dur_s = state.duration_ms / 1000.0
    pct = (state.position_ms / state.duration_ms * 100) if state.duration_ms > 0 else 0

    bar_len = 30
    filled = int(bar_len * (pct / 100.0))
    bar_str = "█" * filled + "░" * (bar_len - filled)

    print("=" * 70)
    print("🎙️ ALEXA LYRICS TV — DIAGNÓSTICO DEL SYNC ENGINE (FASE 1.5)")
    print(f"Estado: {status_icon} | {state.artist} - '{state.track}'")
    print(f"Progreso: [{bar_str}] {pos_s:5.1f}s / {dur_s:5.1f}s ({pct:4.1f}%)")
    print(f"Letras: {state.lyrics_status} ({len(state.lyrics_lines)} versos cargados)")
    if event_msg:
        print(f"Último Evento: {event_msg}")
    print("=" * 70)

    # Ventana de versos (anterior, actual, siguiente)
    idx = state.active_line_index
    lines = state.lyrics_lines

    print("\n--- VENTANA DE LETRAS EN PANTALLA ---")
    if not lines:
        print(f"   [ Sin versos sincronizados: {state.lyrics_status} ]")
    elif idx == -1:
        print("   ♪ ♪ ♪ (Introducción instrumental / Esperando primer verso) ♪ ♪ ♪")
        if len(lines) > 0:
            print(f"      Próximo: '{lines[0]['text']}' en {lines[0]['timestamp_ms']/1000.0:.1f}s")
    else:
        # Verso previo
        if idx > 0:
            prev_l = lines[idx - 1]
            print(f"   - {prev_l['timestamp_ms']/1000.0:5.1f}s: {prev_l['text']}")
        # Verso activo destacado
        active_l = lines[idx]
        print(f" ▶► {active_l['timestamp_ms']/1000.0:5.1f}s: >>> {active_l['text'].upper()} <<<")
        # Próximos versos
        if idx + 1 < len(lines):
            next_l = lines[idx + 1]
            print(f"   + {next_l['timestamp_ms']/1000.0:5.1f}s: {next_l['text']}")
        if idx + 2 < len(lines):
            next2_l = lines[idx + 2]
            print(f"     {next2_l['timestamp_ms']/1000.0:5.1f}s: {next2_l['text']}")

    print("\n" + "=" * 70)


def run_demo_simulation():
    """Ejecuta una simulación completa automatizada de 15 segundos con Queen - Bohemian Rhapsody."""
    print("Iniciando componentes del motor...")
    lyrics_prov = LRCLIBLyricsProvider()
    mock_prov = MockPlaybackProvider()

    engine = SyncEngine(lyrics_provider=lyrics_prov)
    last_event = "Motor Inicializado"

    def on_event(ev):
        nonlocal last_event
        last_event = f"{ev.event_type.value} a las {time.strftime('%H:%M:%S')}"

    engine.add_event_listener(on_event)

    # Cargar canción real en el mock
    mock_prov.load_track(
        track_id="queen_bohemian_real",
        title="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
        duration_ms=354320,
        start_position_ms=0,
        is_playing=True,
    )

    print("Cargando letras desde LRCLIB...")
    # Primera observación
    state = engine.process_observation(mock_prov.get_current_playback())

    # Bucle de simulación por 10 segundos
    t_start = time.time()
    has_paused = False
    has_seeked = False

    while time.time() - t_start < 12.0:
        elapsed = time.time() - t_start

        # En t=3s: simular pausa de 1.5s
        if elapsed >= 3.0 and not has_paused:
            mock_prov.pause()
            engine.process_observation(mock_prov.get_current_playback())
            has_paused = True
            time.sleep(1.2)
            mock_prov.resume()
            engine.process_observation(mock_prov.get_current_playback())

        # En t=7s: simular seek hacia adelante a 24s ("I'm just a poor boy...")
        if elapsed >= 7.0 and not has_seeked:
            mock_prov.seek(24000)
            engine.process_observation(mock_prov.get_current_playback())
            has_seeked = True

        # Tick local para renderizar a 5 fps en terminal
        curr_state = engine.tick()
        render_display(curr_state, last_event)
        time.sleep(0.2)

    print("\n✅ Simulación completada con éxito.")


if __name__ == "__main__":
    run_demo_simulation()
