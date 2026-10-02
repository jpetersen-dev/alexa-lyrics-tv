# 🎙️ Alexa Lyrics TV

> Visualización en tiempo real de letras sincronizadas en televisión no Smart (vía Google Chromecast) para música reproducida mediante Alexa / altavoces Echo en el hogar.

---

## 🏗️ Arquitectura Desacoplada

```
Playback Source (Mock / Alexa / Spotify / Home Assistant)
       │
       ▼
PlaybackProvider (Contrato abstracto)
       │
       ▼
Sync Engine (Orquestador desacoplado)
   ├── PlaybackClock (Interpolación monotónica + tolerancia seek)
   └── LyricsProvider (LRCLIB API + Caché persistente SQLite)
       │
       ▼
SyncedPlaybackState (Payload canónico)
       │
       ▼
Google Cast Web Receiver (CAF v3 en TV vía Chromecast)
```

---

## 🚀 Estado del Proyecto

- **Fase 0**: Auditoría del entorno existente y límites de APIs de Alexa (Completada).
- **Fase 1**: Auditoría de la API de Spotify (`SPOTIFY_POLICY_COMPATIBILITY = UNRESOLVED` debido a restricciones de sincronización audiovisual de Spotify Developer).
- **Fase 1.5**: Construcción independiente del **Sync Engine** (Completada y 100% validada con 27/27 tests pasando).

---

## 🛠️ Ejecución y Pruebas

### 1. Activar entorno virtual
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Ejecutar la suite de tests
```powershell
pytest -v
```

### 3. Ejecutar herramienta de diagnóstico interactiva
```powershell
python src/diagnostic_cli.py
```

---

## 📁 Estructura del Repositorio

- `src/`: Módulos del motor (`mock_provider`, `playback_clock`, `lrc_parser`, `lrclib_provider`, `sync_engine`, `sync_models`).
- `tests/`: Suite exhaustiva de pruebas unitarias y de integración (27 tests).
- `ROADMAP.md`: Plan de fases y seguimiento de tareas.
- `PROJECT_STATE.json`: Estado persistente y telemetría de subsistemas.
- `ARCHITECTURE.md`: Especificación técnica formal y contratos de interfaces.
- `DECISIONS.md`: Registro de Decisiones de Arquitectura (ADRs).
