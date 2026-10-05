# 📐 ARCHITECTURE.md — Alexa Lyrics TV

> **Estado**: Aprobado tras Auditoría de Fase 0  
> **Fecha**: Octubre 2026  
> **Versión**: 1.0.0  

---

## 1. Resumen Ejecutivo y Diagnóstico del Entorno Existente

El objetivo es crear una experiencia tipo "karaoke ambiental automático": cuando Alexa reproduce música en casa, un televisor no Smart conectado mediante Google Chromecast abre automáticamente una interfaz optimizada para TV con las letras sincronizadas en tiempo real.

### 🔍 Auditoría del Microservicio Alexa Existente
En la máquina local opera el microservicio MCP `alexa-skills` (`C:\Users\peter\.gemini\antigravity\mcp_local\alexa-mcp\index.mjs`), respaldado por la CLI oficial `ask.cmd` v2.30.7 y autenticado contra Amazon Developer Console (`~/.ask/cli_config`).

#### Hallazgos y Limitaciones Estrictas de la API de Alexa (Sin inventar capacidades)
1. **Propósito real del microservicio**: Es una herramienta de **gestión y despliegue** (Skill Management API - SMAPI) para crear, modificar, desplegar (`ask deploy`) y simular (`alexa_simulate_skill`) Skills personalizadas.
2. **Capacidad de inspección de reproducción**: **NULA a nivel de SMAPI**. SMAPI no tiene endpoints para consultar el estado de hardware de dispositivos Echo en el hogar.
3. **Sandbox de Alexa Skills Kit (ASK)**:
   - Una Custom Skill solo se ejecuta cuando el usuario la invoca explícitamente (*"Alexa, abre..."*).
   - Si una Custom Skill reproduce audio usando la directiva `AudioPlayer.Play`, la Skill sí recibe eventos de ciclo de vida (`AudioPlayer.PlaybackStarted`, `PlaybackStopped`, etc.) con el `offsetInMilliseconds`.
   - **Limitación fundamental**: Una Custom Skill de Alexa **NO PUEDE** interceptar, espiar ni enterarse de la música que el usuario reproduce fuera de la Skill (por ejemplo, si el usuario dice *"Alexa, pon música en Spotify"* o *"Alexa, reproduce Queen en Amazon Music"*). Amazon aísla estrictamente el reproductor del sistema operativo del Echo de las Skills de terceros por razones de privacidad y seguridad.

---

## 2. ¿Sigue siendo necesario Home Assistant?

Depende exclusivamente de **la fuente de música que utilices en Alexa**:

| Escenario de Reproducción | ¿Requiere Home Assistant? | Mecanismo Técnico | Nivel de Robustez |
| :--- | :---: | :--- | :--- |
| **A. Música reproducida vía Spotify en Alexa** | **NO (Técnicamente directo)** | **Spotify Web API (Spotify Connect)**:<br>Cuando el Echo reproduce Spotify, aparece como dispositivo activo en la API oficial de Spotify (`/v1/me/player`). Proporciona artista, título, álbum, duración, `progress_ms` exacto, estado `is_playing` y timestamp de referencia. | **Técnica: Alta / Política: UNRESOLVED** |
| **B. Música reproducida vía Amazon Music / TuneIn en Alexa** | **SÍ o demonio `alexapy`** | Amazon no ofrece API pública para consultar la reproducción de Amazon Music en un Echo. La única forma conocida en la comunidad domótica es emular la sesión de usuario de `alexa.amazon.com` (como hace la integración `alexa_media_player` de Home Assistant o la librería subyacente `alexapy`). | **Media-Baja (Sujeto a cambios internos de Amazon y expiración de cookies)** |
| **C. Música reproducida a través de una Skill propia** | **NO** | Desarrollar una Skill *"Lyrics Player"* que transmita audio y reporte directamente al backend vía Webhook. | **Alta, pero limitada a audio propio o catálogo libre** |

### 2.1. Reglas Actuales de Spotify Developer Mode (2026)
- **Propietario de la App**: Debe contar obligatoriamente con **Spotify Premium activo**. Una cuenta gratuita no puede crear ni mantener aplicaciones operativas en el portal de desarrolladores.
- **Límite de Usuarios**: Máximo **5 usuarios autorizados** mediante la lista blanca de "User Management".
- **Aplicación para este proyecto**: La aplicación en Spotify Developer debe ser creada y administrada directamente desde la cuenta Premium de Camila.

### 2.2. SPOTIFY_POLICY_COMPATIBILITY: UNRESOLVED (Riesgo Crítico de Políticas)
La documentación oficial de Spotify Web API contiene la siguiente prohibición expresa:
> *"Do not synchronize Spotify content. You may not synchronize any sound recordings with any visual media, including any advertising, film, television program, slideshow, video, or similar content."*

- **Distinción Técnica**:
  - El proyecto lee metadatos y `progress_ms` vía API oficial (`user-read-playback-state`).
  - Las letras provienen de un servicio externo independiente (**LRCLIB**).
  - El audio se reproduce en el altavoz Echo, no en el televisor.
  - Sin embargo, presentar en un televisor un texto desplazándose en correspondencia temporal con la música de Spotify entra en la definición de sincronización audiovisual que los términos de Spotify prohíben a terceros.
- **Estado**: **UNRESOLVED**. Se mantiene la infraestructura experimental desacoplada (`PlaybackProvider`), pero se documenta el riesgo antes de vincular credenciales.

---

## 3. Arquitectura del Sistema Propuesto

```
 ┌────────────────────────────────────────────────────────┐
 │                   ALEXA (Echo Speaker)                 │
 │  (El usuario dice: "Alexa, reproduce Bohemian Rhapsody")│
 └──────────────────────────┬─────────────────────────────┘
                            │
               Reproduce    │ (vía Spotify Connect
                 Audio      │  o Alexa Media Player)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │          DAEMON LOCAL: alexa-lyrics-daemon             │
 │          (Python 3.14 / FastAPI en 192.168.1.88)       │
 │                                                        │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ 1. Media Observer (Polling/Event Listener)       │  │
 │  │    - Título, Artista, Álbum, Duración            │  │
 │  │    - progress_ms, is_playing, timestamp_ref      │  │
 │  └──────────────────────────┬───────────────────────┘  │
 │                             ▼                          │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ 2. Lyrics Engine (Normalizador + Cache SQLite)   │  │
 │  │    - Consulta a LRCLIB (https://lrclib.net)      │  │
 │  │    - Parsea formato LRC a milisegundos           │  │
 │  └──────────────────────────┬───────────────────────┘  │
 │                             ▼                          │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ 3. Sync & State Manager                          │  │
 │  │    - Calcula desfase y prepara paquete de sync   │  │
 │  │    - Control de Pausa, Cambio, Inactividad       │  │
 │  └──────────────────────────┬───────────────────────┘  │
 │                             ▼                          │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ 4. Cast Controller (pychromecast / socket 8009)  │  │
 │  │    - Auto-descubre Chromecast en LAN (mDNS)      │  │
 │  │    - Lanza Custom Web Receiver                   │  │
 │  │    - Transmite vía Cast Custom Channel (TLS)     │  │
 │  └──────────────────────────┬───────────────────────┘  │
 └─────────────────────────────┼──────────────────────────┘
                               │
                               │ Red Local (Protocolo Cast / TLS)
                               │ Mensaje: urn:x-cast:com.alexalyricstv.sync
                               ▼
 ┌────────────────────────────────────────────────────────┐
 │           GOOGLE CHROMECAST + TELEVISOR                │
 │                                                        │
 │   Custom Web Receiver (CAF v3) alojado en Vercel       │
 │   URL: https://alexa-lyrics-tv.vercel.app              │
 │                                                        │
 │   - Recibe payload de canción + LRC + sync point       │
 │   - Reloj local de alta precisión (requestAnimFrame)   │
 │   - Auto-scroll vertical suave                         │
 │   - Modo Karaoke TV (Alto contraste, tipografía 48px+) │
 │   - Auto-cierre por timeout tras inactividad           │
 └────────────────────────────────────────────────────────┘
```

---

## 4. Componentes Detallados

### 4.1. Custom Web Receiver (Google Cast CAF v3) y Controlador Emisor
- **Arquitectura Receptora Híbrida Universal (`web/`)**:
  - **Framework**: Cast Application Framework (CAF) Web Receiver SDK v3.
  - **Doble Canal de Sincronización**:
    - **Modo Cast TV**: Si `window.cast` está disponible (ejecutándose en un Chromecast), se suscribe al Custom Channel con namespace `urn:x-cast:com.alexalyricstv.sync` y recibe los estados transmitidos por el daemon local sobre el canal TLS de Cast.
    - **Modo Web / Navegador / Móvil**: Si corre en un navegador estándar (Chrome, Safari, Cast Tab), abre un WebSocket a `/ws/playback`.
  - Ambos canales alimentan la misma función `applyPlaybackState()` y el reloj interpolador local a 60 fps (`requestAnimationFrame` + `performance.now()`).
  - **Alojamiento (Hosting)**:
    - Configurado para **Vercel** (`web/vercel.json`) cumpliendo el requisito estricto de HTTPS público y encabezados CORS necesarios para Cast.

- **Controlador Emisor Cast Backend (`src/cast_controller.py`)**:
  - `LyricsCastController`: Extiende `pychromecast.controllers.BaseController` registrando el namespace `urn:x-cast:com.alexalyricstv.sync`.
  - `CastManager`:
    - Descubre dispositivos Chromecast en la red local vía mDNS (`zeroconf`) o mediante conexión directa por dirección IP.
    - Conecta mediante socket seguro TLS (puerto 8009).
    - Lanza la aplicación mediante `start_app(app_id)` y monitoriza su ciclo de vida.
    - Transmite en tiempo real el payload canónico `SyncedPlaybackState`.
  - **Seguridad y Aislamiento**:
    - Al viajar los datos por el socket local TLS del protocolo Cast, no hay exposición de credenciales en la red externa ni problemas de *Mixed Content*.

### 4.2. Motor de Letras (Lyrics Engine + LRCLIB)
- **Endpoint**: `https://lrclib.net/api/get?artist_name={artist}&track_name={track}&album_name={album}&duration={duration}`
- **Normalización de Metadatos**:
  - Limpieza de sufijos como `- Remastered 2011`, `(feat. ...)`, `[Live]`, `(Deluxe Edition)`.
  - Búsqueda primaria exacta; si falla, búsqueda secundaria relajada mediante `/api/search`.
- **Caché**:
  - Base de datos local SQLite (`lyrics_cache.db`).
  - Si la canción ya fue consultada previamente, la respuesta es inmediata (< 2ms) y funciona incluso si se interrumpe temporalmente la conexión a Internet.

### 4.3. Motor de Sincronización (Sync Engine & PlaybackClock)
- **Principio**: **Zero Network Spam** e **Independencia de Fuente**.
- **Componentes Validados (Fase 1.5)**:
  1. `PlaybackClock`: Emplea `time.monotonic()` para avanzar la posición de forma local continua. Se congela ante `is_playing = False` y compensa latencias de red. Si detecta saltos superiores a 2.500 ms, los clasifica como *seek* y recalibra sin interpolación residual.
  2. `LRCParser`: Parsea timestamps con centésimas (`.xx`), milésimas (`.xxx`), etiquetas de offset global `[offset:+/-ms]` y timestamps múltiples en una misma línea (`[00:10.00][00:20.00]Coro`), ordenando la salida cronológicamente.
  3. `get_active_line`: Función determinista basada en búsqueda binaria sobre los versos ordenados, identificando `is_intro` (antes del primer verso), coincidencia exacta, intervalos y `is_outro`.
  4. `SyncEngine`: Orquestador desacoplado que gestiona transiciones de estado, invalida letras ante cambio de canción y emite eventos internos (`TRACK_CHANGED`, `PLAYBACK_PAUSED`, `PLAYBACK_RESUMED`, `PLAYBACK_SEEKED`, `LYRICS_READY`).
- **Contrato Canónico de Salida (`SyncedPlaybackState`)**:
  El payload emitido hacia el Cast Web Receiver en el televisor:
  ```json
  {
    "track": "Bohemian Rhapsody",
    "artist": "Queen",
    "album": "A Night at the Opera",
    "duration_ms": 354320,
    "position_ms": 45200,
    "is_playing": true,
    "lyrics_status": "SYNCED",
    "lyrics_lines": [
      { "timestamp_ms": 150, "text": "Is this the real life?" },
      { "timestamp_ms": 7130, "text": "Is this just fantasy?" }
    ],
    "active_line_index": 0,
    "active_line_text": "Is this the real life?",
    "next_line_text": "Is this just fantasy?",
    "generated_at": 1727828450.123,
    "reference_timestamp_ms": 1727828450123
  }
  ```
- **Cálculo de Renderizado en el Receiver (TV)**:
  ```javascript
  const now = Date.now();
  const elapsedSincePulse = (state.is_playing) ? (now - state.reference_timestamp_ms) : 0;
  const currentSongPosition = state.position_ms + elapsedSincePulse;
  ```
  Esto garantiza scroll a 60 fps con suavidad nativa, sin jitter y sin saturar la red local.

### 4.4. Control Automático de Chromecast (Auto-Lifecycle)
- **Arranque automático**:
  - Al detectar `state == PLAYING`, el backend busca el Chromecast en la red local mediante mDNS y lanza la aplicación Receiver en la TV.
- **Pausa / Reanudación**:
  - Al detectar `PAUSED`, el backend envía estado `PAUSED`; la interfaz congela el scroll y atenúa sutilmente la pantalla.
- **Cierre automático (Auto-sleep)**:
  - Si transcurren más de 3 minutos en estado `PAUSED` o `IDLE`, el backend libera la sesión de Cast para que el televisor vuelva a su protector de pantalla ambiental o modo reposo.

### 4.5. Servidor de Transporte (FastAPI + WebSockets) y Visor Web Local (React + Vite)
- **Servidor Asíncrono (`src/server.py`)**:
  - FastAPI gestiona el ciclo de vida del `SyncEngine` mediante el gestor de contexto `lifespan`.
  - Un bucle de sincronización en segundo plano (`background_sync_loop`) evalúa el estado del reproductor cada 150 ms sin bloquear el hilo principal.
  - **Canal WebSocket `/ws/playback`**:
    - Conexión inicial: Entrega inmediata del `SyncedPlaybackState` completo.
    - Política de emisión reactiva (Zero Network Spam):
      1. Transición de estado de reproducción (`is_playing` cambia).
      2. Cambio de pista (`track` cambia).
      3. Transición de verso activo (`active_line_index` cambia).
      4. Pulso de anclaje periódico cada 3 segundos (`reference_timestamp_ms` + `position_ms`).
  - **Endpoints de Control y Diagnóstico**:
    - `GET /api/status`: Estado del motor, clientes conectados y última sincronización.
    - `POST /api/mock/play`, `pause`, `resume`, `seek`, `next`, `load`: Control determinista para desarrollo y pruebas.
  - **Distribución Estática Unificada**:
    - Montaje estático de `web/dist` en la raíz `/` de FastAPI, permitiendo servir la interfaz y los WebSockets desde un único puerto (8000).

- **Visor Web React 19 (`web/`)**:
  - `useSyncedLyrics`: Hook personalizado que gestiona el WebSocket, la reconexión exponencial y el cálculo local continuo a 60 fps mediante `requestAnimationFrame` y `performance.now()`.
  - `KaraokeView`: Componente de pantalla completa optimizado para televisores con tipografía masiva (48px+), efectos de brillo/glow sobre la línea cantada, desplazamiento vertical continuo centrado y modo ambiental de reloj cuando está en pausa.
  - `DiagnosticPanel`: Barra de control flotante que permite disparar cambios de estado en el backend, seleccionar fuentes de audio e inspeccionar letras en vivo contra LRCLIB.

### 4.6. Orquestador de Reproducción y Ciclo de Vida Automático (AutoCast)
- **`PlaybackOrchestrator` (`src/playback_orchestrator.py`)**:
  - Hub central que desacopla la fuente de audio del `SyncEngine`.
  - Conmutador en caliente de proveedores (`mock`, `webhook`, `homeassistant`, `spotify`):
    - `WebhookPlaybackProvider`: Permite push HTTP (`POST /api/playback/update`) desde cualquier servicio o automatización.
    - `HomeAssistantPlaybackProvider`: Consulta altavoces Echo a través de la integración `alexa_media_player` de Home Assistant.
    - `SpotifyPlaybackProvider`: Adaptador oficial Spotify Connect (`/v1/me/player`).
    - `MockPlaybackProvider`: Arnés determinista para pruebas automatizadas.
  - **Reglas de AutoCast (Control Autónomo de Pantalla)**:
    1. **Auto-Lanzamiento**: Al detectar `is_playing = True`, si AutoCast está habilitado, conecta automáticamente al Chromecast y lanza la app en el televisor.
    2. **Auto-Cierre por Inactividad**: Al transcurrir más de 180 segundos en pausa o silencio, invoca `quit_app()` para apagar la sesión y devolver el televisor al protector de pantalla o reposo.
    3. **Keep-Alive**: Emisión de pulsos cada 3 segundos garantizando la continuidad de la conexión TLS de Cast sin caídas.

### 4.7. Configuración Persistente y Ejecución en Segundo Plano (Windows Daemon)
- **Gestor de Configuración Persistente (`src/config_manager.py`)**:
  - Almacena parámetros operativos en formato JSON (`config.json`):
    - `default_provider`: Proveedor inicial de reproducción (`mock`, `webhook`, `homeassistant`, `spotify`).
    - `autocast_enabled`: Flag maestro para auto-lanzar y auto-cerrar en el televisor.
    - `target_cast_device` / `target_cast_host`: Identificador y dirección IP del Chromecast preferido.
    - `idle_timeout_seconds`: Temporizador de inactividad antes de liberar el televisor (por defecto 180s).
    - `keep_alive_interval_seconds`: Intervalo de paquetes PING ligeros a través del Custom Channel (por defecto 15s).
    - Parámetros de conexión de Home Assistant (`hass_url`, `hass_token`, `hass_alexa_entity`).
  - Endpoints REST en caliente: `GET /api/config` y `POST /api/config`.
- **Caché de Dispositivos Cast en Memoria**:
  - `CastManager` almacena mapeos nombre -> IP (`_device_cache`) para reconectar en <100 ms ante nuevas pistas, evitando la espera de 5 segundos de escaneo mDNS zeroconf.
- **Suite de Scripts para Windows (`scripts/`)**:
  - `start_daemon.bat`: Ejecución en primer plano con consola para diagnóstico y desarrollo.
  - `start_hidden.vbs`: Lanzador silencioso que arranca el proceso Python/Uvicorn sin ventana visible en el escritorio.
  - `stop_daemon.bat`: Detección y terminación forzada del proceso que ocupa el puerto 8000.
  - `install_startup.bat`: Creación automática del acceso directo silencioso en la carpeta de inicio de Windows (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`).
  - `uninstall_startup.bat`: Eliminación limpia del acceso directo de arranque.

### 4.8. Robustez, Resiliencia ante Fallos y Estrategia Offline
- **Tolerancia a Cortes de Red (Estrategia de Caché)**:
  - `LRCLIBLyricsProvider` consulta primero `lyrics_cache.db` (SQLite). Si Internet cae, las canciones previamente reproducidas se siguen sincronizando localmente sin interrupciones (`is_cached: true`).
  - Si la canción no estaba en caché y la red falla (timeout, conexión rechazada, HTTP 429/500), el proveedor emite `LyricsStatus.ERROR` sin propagar excepciones que interrumpan el bucle de sincronización ni el reloj.
- **Degradación Elegante en Pantalla (`web/src/components/KaraokeView.tsx`)**:
  - `NO_LYRICS`: Canciones instrumentales o fuera de catálogo muestran interfaz limpia con nota musical y carátula.
  - `UNSYNCED`: Canciones con solo letra plana se despliegan en modo lectura vertical.
  - `ERROR`: Modo ambiental de música con aviso informativo ("Sin conexión al catálogo de letras").
  - `IDLE`: Reloj ambiental minimalista en reposo.
- **Desconexión Defensiva de Cast**:
  - `CastManager` captura fallos de socket (`BrokenPipeError`, `ConnectionResetError`) tanto en `send_playback_state` como en `send_keep_alive`, forzando `disconnect()` inmediato para evitar estados fantasma.
- **Reconexión Automática con Throttle**:
  - `PlaybackOrchestrator` implementa un límite de reintento de 10 segundos para buscar y reconectar el Chromecast mientras haya música activa, evitando saturar la CPU o la red mDNS si el televisor está apagado. Al encenderse, la conexión se establece automáticamente.

---

## 5. Decisiones Técnicas Fundamentales

1. **Lenguaje Backend**: **Python 3.14** con `pychromecast`, `FastAPI` y `websockets`.
   - `pychromecast` para control de Cast local (puerto 8009 TLS).
   - `FastAPI` para APIs de desarrollo, WebSockets de baja latencia y servicio de la SPA.
2. **Frontend Receiver / Visor**: React 19 + TypeScript + Vite, optimizado para televisores 1080p/4K, convertible a Cast Custom Web Receiver (CAF v3) y desplegable en Vercel con HTTPS.
3. **Manejo de Secretos**: Ningún token o secreto se transmite jamás al Chromecast ni se expone en el código cliente.



