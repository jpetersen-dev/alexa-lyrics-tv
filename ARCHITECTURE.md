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

### 4.1. Custom Web Receiver (Google Cast)
- **Framework**: Cast Application Framework (CAF) Web Receiver SDK v3.
- **Frontend**: React 19 o Vanilla HTML5 + CSS ultraligero con Tailwind CSS para máxima fluidez en el procesador limitado del Chromecast.
- **Canal de Comunicación**:
  - Namespace dedicado: `urn:x-cast:com.alexalyricstv.sync`
  - Utiliza el bus de mensajes nativo de Google Cast (`castReceiverContext.addCustomMessageListener(...)`).
  - **Ventaja de seguridad y red**: Al viajar la información a través del canal Cast local abierto por el backend emisor (puerto 8009 TLS), **no se generan problemas de Mixed Content ni CORS** entre la página HTTPS del Receiver y la máquina local.
- **Alojamiento (Hosting)**:
  - **Vercel** proporciona HTTPS válido obligatorio por Chromecast, despliegue continuo y CDN global con latencia despreciable.

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
  - `DiagnosticPanel`: Barra de control flotante que permite disparar cambios de estado en el backend e inspeccionar letras en vivo contra LRCLIB.

---

## 5. Decisiones Técnicas Fundamentales

1. **Lenguaje Backend**: **Python 3.14** con `pychromecast`, `FastAPI` y `websockets`.
   - `pychromecast` para control de Cast local (puerto 8009 TLS).
   - `FastAPI` para APIs de desarrollo, WebSockets de baja latencia y servicio de la SPA.
2. **Frontend Receiver / Visor**: React 19 + TypeScript + Vite, optimizado para televisores 1080p/4K, convertible a Cast Custom Web Receiver (CAF v3) y desplegable en Vercel con HTTPS.
3. **Manejo de Secretos**: Ningún token o secreto se transmite jamás al Chromecast ni se expone en el código cliente.

