# 📜 DECISIONS.md — Registro de Decisiones de Arquitectura (ADR)

> Proyecto: **ALEXA LYRICS TV**  
> Documento de Decisiones Técnicas y Justificaciones

---

## ADR 001: Estrategia de Captura de Reproducción de Alexa (Límites de la API oficial)

### Contexto
Se evaluó si el microservicio existente `alexa-skills` o una Custom Skill de Alexa podían reportar la música reproducida en los altavoces Echo cuando el usuario solicita canciones de forma habitual (*"Alexa, pon música"*).

### Hallazgo y Decisión
- **Hallazgo**: La Skill Management API (SMAPI) y el Alexa Skills Kit (ASK) imponen un aislamiento estricto de sandbox. Ninguna Skill de terceros puede espiar o recibir eventos de la música reproducida por servicios de streaming certificados (Spotify, Amazon Music) fuera de la propia Skill.
- **Decisión**: Implementar una arquitectura de **Observadores Desacoplados (Adapter Pattern)** en el Daemon local:
  1. **Adaptador Spotify Connect (Principal / Experimental)**: Consulta directa a la API de Spotify (`/v1/me/player`).
  2. **Adaptador Alexa Media Player / WebSocket (Secundario / Alternativo)**: Conexión domótica vía Home Assistant o demonio `alexapy`.
  3. **Adaptador Custom Audio Skill (Opcional)**: Skill dedicada para audio libre de DRM.
  4. **Adaptador Mock (Simulación Determinista)**: Para desarrollo y pruebas offline completas.

---

## ADR 002: Elección del Stack del Daemon Backend (Python 3.14 + pychromecast)

### Decisión
Adoptar **Python 3.14** para el daemon local `alexa-lyrics-daemon`, utilizando `pychromecast` para la gestión de Cast y `requests` / `sqlite3` para el motor de letras y adaptadores.

---

## ADR 003: Hosting y Modelo de Despliegue del Custom Web Receiver en Vercel

### Decisión
- Desarrollar la interfaz del Receiver como una Single Page Application (SPA) ultraligera.
- Desplegar la aplicación estática en **Vercel** (`https://alexa-lyrics-tv.vercel.app`) para cumplir el requisito estricto de HTTPS público de Google Cast.

---

## ADR 004: Algoritmo de Sincronización basado en Ancla Temporal (Reference Timestamp)

### Decisión
Implementar el algoritmo **Reference Timestamp Interpolation**: el backend envía un paquete únicamente ante eventos de transporte o pulso cada 5 segundos; el Receiver interpola a 60 fps mediante `requestAnimationFrame`.

---

## ADR 005: Motor de Letras y Estrategia de Caché con LRCLIB

### Decisión
1. Normalización regex previa de metadatos (eliminación de sufijos `Remastered`, `Live`, `feat.`).
2. Caché persistente en SQLite local (`lyrics_cache.db`).
3. Formato numérico normalizado de líneas `{ timestamp_ms, text }`.

---

## ADR 006: Evaluación de Políticas de Spotify y Reglas de Development Mode (2026)

### Contexto
Se auditó la documentación oficial actualizada de Spotify for Developers (febrero-octubre 2026) para contrastar los requisitos de Development Mode y las restricciones de uso sobre sincronización.

### 1. Reglas Actuales de Development Mode (2026)
- **Propiedad con Premium Obligatoria**: El creador de la aplicación en el Spotify Developer Dashboard **debe poseer una suscripción activa a Spotify Premium**. Si la suscripción expira o la cuenta es Free, la app deja de funcionar.
  - *Consecuencia*: La cuenta gratuita del desarrollador no puede crear ni gestionar la aplicación; **debe ser creada directamente por Camila** (titular de la cuenta Premium).
- **Límite de Usuarios**: Máximo **5 usuarios autorizados** (reducido del histórico de 25). Los usuarios deben figurar en la allowlist de "User Management".

### 2. Cláusula de Sincronización ("Do Not Synchronize")
La documentación y términos de Spotify Developer establecen textualmente:
> *"Do not synchronize Spotify content. You may not synchronize any sound recordings with any visual media, including any advertising, film, television program, slideshow, video, or similar content."*

### 3. Estado: `SPOTIFY_POLICY_COMPATIBILITY`: UNRESOLVED
- No es posible declarar el caso como `COMPATIBLE` de forma transparente, ya que la letra literal de la política veta la sincronización con pantallas/televisión.
- Se mantiene congelada la integración de Spotify Developer mientras se avanza con infraestructura neutral.

---

## ADR 007: Arquitectura Desacoplada del Sync Engine e Independencia de Fuente de Audio

### Contexto
Para evitar que el bloqueo de políticas de Spotify detenga el proyecto, se decidió construir y validar todo el núcleo de sincronización de letras de forma 100% independiente de cualquier proveedor externo.

### Decisión
1. **Desacoplamiento Estricto**:
   - `SyncEngine` solo consume la interfaz abstracta `PlaybackProvider`.
   - Se implementó `MockPlaybackProvider` para controlar y simular cualquier escenario musical con precisión de milisegundos.
2. **Fuente de Tiempo Monotónica (`PlaybackClock`)**:
   - Utiliza `time.monotonic()` para calcular el avance temporal continuo:
     $$\text{posición actual} = \text{progress\_ms} + (\text{time.monotonic}() - \text{anchor\_monotonic})$$
   - Si `is_playing == False`, la posición se congela milimétricamente.
   - Detecta *seeks* automáticamente ante diferencias superiores a 2.500 ms y recalibra instantáneamente sin arrastre.
   - Compensa latencias de transporte de red conocidas.
3. **Parser y Resolución Determinista de Versos**:
   - `parse_lrc()` procesa centésimas, milésimas, offsets globales y timestamps múltiples en una misma línea.
   - `get_active_line()` implementa búsqueda binaria sobre versos ordenados cronológicamente, definiendo estados inequívocos para intro (`index = -1`), coincidencia exacta, intervalos y outro.
4. **Contrato de Salida Canónico (`SyncedPlaybackState`)**:
   - Estructura pura que desacopla el reproductor y las letras del Cast Web Receiver:
     `{ track, artist, duration_ms, position_ms, is_playing, lyrics_status, lyrics_lines, active_line_index, active_line_text, next_line_text, reference_timestamp_ms }`
   - El Chromecast no tiene conocimiento alguno de Spotify, Alexa ni LRCLIB.

---

## ADR 008: Servidor de Transporte en Tiempo Real (FastAPI + WebSockets) y Visor Web Local (React 19 + TypeScript + Vite)

### Contexto
Para validar visualmente el comportamiento del motor de sincronización antes de integrar Google Cast (CAF v3) y resolver credenciales de Spotify, era necesario implementar un canal de transporte en tiempo real y una interfaz web local optimizada para TV.

### Decisión
1. **Transporte Backend con FastAPI + WebSockets (`src/server.py`)**:
   - Implementar un servidor asíncrono con `FastAPI` y `websockets`.
   - Canal WebSocket `/ws/playback` con política **Zero Network Spam**:
     - Envío inmediato del estado actual al conectar un nuevo cliente.
     - Emisión reactiva únicamente ante cambios de estado (`is_playing`, `track`) o transición de verso (`active_line_index`).
     - Pulso de sincronización de seguridad cada 3 segundos (`reference_timestamp_ms` + `position_ms`) para corregir cualquier deriva acumulada.
   - Bucle de fondo no bloqueante (`asyncio.sleep(0.150)`) ejecutado durante el ciclo de vida del servidor (`lifespan`).
   - Endpoints REST `/api/mock/*` para control determinista del reproductor y `/api/status` para telemetría.
   - Montaje estático de `web/dist` en la raíz `/` para operar en un único puerto (`8000`) sin proxies inversos en producción local.

2. **Visor Web React 19 + TypeScript + Vite (`web/`)**:
   - **Interpolación Cliente a 60 fps (`useSyncedLyrics`)**:
     - El cliente calcula la posición continua usando `requestAnimationFrame` y deltas de tiempo local con `performance.now()`.
     - Resolución de verso activo en cliente mediante búsqueda binaria rápida sobre `lyrics_lines`.
     - Cero dependencia de transmisiones de red a 60 fps, minimizando uso de CPU y ancho de banda en dispositivos ligeros como Chromecast.
   - **Diseño de Interfaz TV (`KaraokeView`)**:
     - Modo oscuro de alto contraste con fondo `#08080a` y tarjetas de vidrio translúcido (*glassmorphic*).
     - Tipografía masiva de 48px+ con sombras brillantes luminiscentes para legibilidad a 3 metros.
     - Auto-scroll vertical centrado suave utilizando `scrollIntoView({ behavior: 'smooth', block: 'center' })`.
     - Pantalla ambiental con reloj digital grande cuando la reproducción está en pausa o detenida.
     - Panel de diagnóstico flotante (`DiagnosticPanel`) colapsable para pruebas de campo e inspección de LRCLIB en vivo.

---

## ADR 009: Arquitectura Híbrida Universal para Google Cast Custom Web Receiver (CAF v3) y Fallback WebSocket

### Contexto
El despliegue en Google Chromecast requiere compatibilidad estricta con el Cast Application Framework (CAF v3) y transmisión a través de canales TLS seguros (`urn:x-cast:com.alexalyricstv.sync`), mientras que para el desarrollo local, pruebas móviles y entornos sin registrar en Google Cast Developer Console ($5 USD) se requiere acceso mediante navegadores estándar y WebSockets.

### Decisión
1. **Receptor Web Universal Híbrido (`web/`)**:
   - Se integró el SDK oficial de Google Cast CAF v3 en `web/index.html`:
     `<script src="//www.gstatic.com/cast/sdk/libs/caf_receiver/v1.0/cast_receiver_framework.js"></script>`
   - `useSyncedLyrics` detecta dinámicamente si `window.cast` está disponible:
     - Si opera en Chromecast (CAF v3 activo): Escucha el Custom Channel `urn:x-cast:com.alexalyricstv.sync` alimentado por el daemon local.
     - Si opera en navegador estándar (PC, móvil, tablet): Conecta directamente al canal WebSocket `/ws/playback`.
   - Ambos canales alimentan la misma función unificada `applyPlaybackState()`, manteniendo la interpolación fluida a 60 fps intacta.
2. **Controlador Emisor Cast Backend (`src/cast_controller.py`)**:
   - Implementa `LyricsCastController` extendiendo `pychromecast.controllers.BaseController`.
   - `CastManager` gestiona descubrimiento de dispositivos en la red local (mDNS zeroconf) y conexiones directas por dirección IP.
   - Enlace bidireccional en `src/server.py`: cada actualización emitida a WebSockets se replica de forma no bloqueante a los dispositivos Cast activos.
   - Configuración de empaquetado para despliegue en Vercel con HTTPS mediante `web/vercel.json`.

---

## ADR 010: Orquestación Universal de Fuentes de Audio y Ciclo de Vida Automático de TV (AutoCast)

### Contexto
Para alcanzar la experiencia de karaoke ambiental automático descrita en la misión del proyecto sin atarse de forma irreversible a Spotify (pendiente de resolución de políticas) ni requerir intervención manual constante para encender y apagar el televisor, se requería una capa unificadora capaz de coordinar múltiples observadores de audio y automatizar el ciclo de vida del Chromecast.

### Decisión
1. **Orquestador Universal de Reproducción (`src/playback_orchestrator.py`)**:
   - Actúa como hub central entre cualquier fuente de audio y el `SyncEngine`.
   - Soporta 4 adaptadores desacoplados e intercambiables en caliente:
     - `mock`: Simulador determinista para desarrollo y pruebas.
     - `webhook`: Endpoint HTTP `POST /api/playback/update` para recibir eventos en tiempo real desde Custom Skills, scripts de automatización o webhooks locales.
     - `homeassistant`: Consulta a entidades `media_player.echo_*` vía API REST de Home Assistant (integración `alexa_media_player`).
     - `spotify`: Conexión directa a Spotify Connect Web API si se configuran credenciales.
2. **Ciclo de Vida Automático de Cast (AutoCast)**:
   - **Auto-Lanzamiento**: Al detectar una transición de estado a `is_playing = True`, si AutoCast está habilitado y el Chromecast no está conectado, el orquestador se conecta al televisor por mDNS o IP, lanza el Custom Web Receiver y transmite inmediatamente el estado actual.
   - **Auto-Cierre por Inactividad**: Si la reproducción permanece pausada o inactiva por más de un tiempo configurable (por defecto 180 segundos / 3 minutos), el daemon invoca `quit_app()` y desconecta la sesión, permitiendo que el Chromecast y el televisor vuelvan al modo ambiental/reposo de bajo consumo.
   - **Keep-Alive**: Cada 3 segundos se emite un pulso temporal de anclaje para refrescar el canal de Cast y evitar desconexiones por timeout de inactividad de socket.

