# 🗺️ ROADMAP.md — Alexa Lyrics TV

> Proyecto: **ALEXA LYRICS TV**  
> Convención de Estados:
> - `[ ]` Pendiente
> - `[~]` En progreso
> - `[x]` Completada (Solo con evidencia documentada)

---

## 📌 Fase 0 — Auditoría del Entorno Existente

- **Objetivo**: Inspeccionar la máquina local, el microservicio Alexa, las capacidades reales de la API de Alexa, la conectividad con LRCLIB y la viabilidad de Google Cast, determinando la arquitectura más simple, robusta y mantenible.
- **Tareas**:
  - [x] Inspeccionar el microservicio local de Alexa (`alexa-skills` MCP y `ask.cmd`).
  - [x] Auditar credenciales y autenticación en `~/.ask/cli_config`.
  - [x] Determinar qué datos de reproducción puede y no puede obtener Alexa SMAPI/ASK (documentar límites de sandbox).
  - [x] Evaluar si Home Assistant sigue siendo estrictamente necesario o si existen alternativas más directas.
  - [x] Probar conectividad y respuestas de la API de LRCLIB.
  - [x] Investigar requisitos técnicos del Cast Web Receiver SDK y restricciones HTTPS.
  - [x] Crear estructura de documentación persistente (`ROADMAP.md`, `PROJECT_STATE.json`, `DECISIONS.md`, `ARCHITECTURE.md`).
  - [x] Definir reglas de proyecto y evaluar Skills de Antigravity.
- **Criterios de Aceptación**:
  - Informe técnico transparente sobre el alcance real del microservicio Alexa.
  - Determinación fundada sobre la necesidad de Home Assistant.
  - Archivos de documentación creados y consistentes.
- **Pruebas Realizadas**:
  - Ejecución de `alexa_check_auth` y `alexa_list_skills` (conexión activa con Amazon Developer Console).
  - Consulta directa a LRCLIB (`Queen - Bohemian Rhapsody`) validando obtención de timestamps en formato `[mm:ss.xx]`.
  - Escaneo de red local verificando IP `192.168.1.88` y ausencia de demonios Docker.
- **Evidencia**:
  - `C:\Users\peter\.gemini\antigravity\mcp_local\alexa-mcp\index.mjs` analizado (855 líneas inspeccionadas).
  - Test exitoso en consola con LRCLIB devolviendo `syncedLyrics: True`.
  - Archivos base creados en `d:\Projects (Local)\alexa-lyrics-tv\`.
- **Riesgos**:
  - El usuario puede esperar que una Skill de Alexa pueda "espiar" Spotify/Amazon Music cuando la plataforma de Amazon lo prohíbe explícitamente. Se mitiga mediante el desacoplamiento con adaptadores específicos.

---

## 📌 Fase 1 — Validación de Fuente de Reproducción (Auditoría de Spotify)

- **Objetivo**: Determinar experimental y contractualmente si Spotify Web API puede utilizarse de forma fiable y conforme a sus términos para sincronizar letras con la música que reproduce Alexa en un televisor.
- **Estado de Compatibilidad de Políticas**:
  - `SPOTIFY_POLICY_COMPATIBILITY`: **UNRESOLVED** (Riesgo Alto).
  - Cláusula analizada: *"Do not synchronize Spotify content. You may not synchronize any sound recordings with any visual media, including any advertising, film, television program, slideshow, video, or similar content."*
  - Reglas de Developer Mode (2026): Propietario con Spotify Premium obligatorio, máximo **5 usuarios autorizados** mediante User Management allowlist. La cuenta gratuita del desarrollador NO puede ser la propietaria; debe pertenecer a Camila.
- **Tareas**:
  - [x] Investigar API actual de Spotify (febrero-octubre 2026) y restricciones de Development Mode (máx 5 usuarios, Premium obligatorio para el creador).
  - [x] Auditar cláusula de sincronización audiovisual y términos de la plataforma.
  - [x] Implementar arquitectura experimental desacoplada (`PlaybackState`, `PlaybackProvider`, `SpotifyPlaybackProvider`).
  - [x] Implementar servidor OAuth local (`src/oauth_server.py`) y arnés de pruebas (`src/test_playback_observer.py`).
  - [~] Auditoría de compatibilidad de uso: Resolver si el caso de uso es viable bajo los términos de Spotify o requiere pivotar.
  - [ ] Crear la App en Spotify Developer Dashboard directamente desde la cuenta Premium de Camila (pendiente de resolución de compatibilidad).
  - [ ] Autorizar cuenta Spotify Premium de Camila y almacenar tokens de forma segura en backend local.
  - [ ] Ejecutar Pruebas A, B, C, D y E con Alexa.
  - [ ] Medir y documentar latencias reales T0 -> T1.
- **Criterios de Aceptación**:
  - Resolución justificada de `SPOTIFY_POLICY_COMPATIBILITY` antes de operar credenciales.
  - Obtención demostrada de metadatos, `progress_ms`, `is_playing` y dispositivo Echo activo sin violar términos o habiendo asumido el riesgo operativo.
- **Riesgos Identificados**:
  - Revocación de API por parte de Spotify si sus sistemas automatizados o revisiones consideran que el streaming a TV con letras sincronizadas viola la prohibición de sincronización con "television program / visual media".
  - Imposibilidad de que la cuenta gratuita del desarrollador cree o administre la app en el Developer Dashboard.
- **Pruebas**:
  - Reproducir canción -> pausar -> reanudar -> cambiar canción; el script debe reflejar todos los estados.
- **Evidencia**:
  - Log de consola con timestamps y salida JSON estructurada.
- **Riesgos**:
  - Expiración de tokens de sesión; se debe implementar renovación automática.

---

## 📌 Fase 1.5 — Construcción Independiente del Sync Engine

- **Objetivo**: Construir y validar todo el núcleo técnico del proyecto sin depender de Spotify ni Alexa, garantizando que el motor de sincronización sea desacoplado, resiliente y compatible con cualquier PlaybackProvider.
- **Tareas**:
  - [x] Implementar `MockPlaybackProvider` determinista con controles (`play`, `pause`, `resume`, `seek`, `next_track`).
  - [x] Implementar `PlaybackClock` con interpolación monotónica local (`time.monotonic`), tolerancia a latencia de red y detección de seek.
  - [x] Implementar `LRCParser` con soporte completo para centésimas, milésimas, desplazamientos globales `[offset:+/-ms]`, timestamps múltiples en una misma línea y ordenamiento cronológico.
  - [x] Implementar función determinista `get_active_line` con cobertura de casos borde (intro, coincidencia exacta, intervalos y outro).
  - [x] Implementar abstracción `LyricsProvider` e integración `LRCLIBLyricsProvider` con normalización de títulos y caché local persistente en SQLite (`lyrics_cache.db`).
  - [x] Implementar `SyncEngine` como orquestador desacoplado con bus de eventos internos (`TRACK_CHANGED`, `PLAYBACK_PAUSED`, `PLAYBACK_RESUMED`, `PLAYBACK_SEEKED`, `LYRICS_READY`, etc.).
  - [x] Definir contrato de salida canónico `SyncedPlaybackState` para el Cast Web Receiver.
  - [x] Construir suite de 27 tests automatizados en `pytest` cubriendo los 11 escenarios requeridos y 5 simulaciones de error.
  - [x] Construir herramienta instrumental de diagnóstico por consola (`src/diagnostic_cli.py`).
- **Criterios de Aceptación**:
  - Posición continua estimada sin saltos ni dependencia de polling constante.
  - Pausa y reanudación congelan y reactivan la posición con total precisión.
  - Seek detectado y recalibrado instantáneamente sin interpolaciones erróneas.
  - Letras de LRCLIB parseadas y cacheadas en SQLite.
  - 100% de tests pasando en entorno local.
- **Pruebas Realizadas**:
  - **Test 1**: Canción comenzando en 0 ms (Intro detectada correctamente).
  - **Test 2**: Canción comenzando en 30.000 ms (Línea activa exacta resuelta).
  - **Test 3**: Pausa durante verso (Posición congelada milimétricamente).
  - **Test 4**: Reanudación (Avance monotónico continuo).
  - **Test 5 & 6**: Seek adelante (10s -> 42s) y atrás (45s -> 5s) con eventos `PLAYBACK_SEEKED`.
  - **Test 7**: Cambio de pista con invalidación inmediata de letras.
  - **Test 8 & 9**: Canción instrumental / sin letra y canción con solo letra plana.
  - **Test 10**: Compensación de retardo artificial de red (+350 ms).
  - **Test 11**: Ráfagas irregulares de observación (jitter de red).
  - **Simulaciones de Error**: Timeout LRCLIB, HTTP 429, HTTP 500 y pérdida de proveedor (204).
- **Evidencia**:
  - `pytest -v`: **27 passed in 1.84s** en [`tests/`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/tests).
  - Simulación ejecutada en [`src/diagnostic_cli.py`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/src/diagnostic_cli.py) con Queen - Bohemian Rhapsody.
- **Riesgos Mitigados**:
  - Cero acoplamiento a Spotify: el sistema funciona autónomamente con mocks, Home Assistant o cualquier fuente de audio futura.

---

## 📌 Fase 2 — Servidor de Transporte (FastAPI + WebSockets) y Visor Web Local (React + Vite)

- **Objetivo**: Construir la capa de transporte en tiempo real y el visor web local para validar visualmente la experiencia de karaoke antes de abordar la integración con Google Cast.
- **Tareas**:
  - [x] Registrar formalmente `pytest`, `pytest-asyncio`, `httpx` en `requirements.txt` y `requirements-dev.txt`.
  - [x] Implementar servidor backend FastAPI (`src/server.py`) con lifespan async y bucle de fondo a 150ms.
  - [x] Implementar canal WebSocket `/ws/playback` con política Zero Network Spam: estado inicial inmediato + emisiones reactivas ante cambio de verso/estado + pulso de sincronización cada 3 segundos.
  - [x] Implementar endpoints REST `/api/mock/*` (`play`, `pause`, `resume`, `seek`, `next`, `load`) para el arnés de diagnóstico.
  - [x] Servir la aplicación web estática de producción (`web/dist`) directamente desde la raíz (`/`) de FastAPI.
  - [x] Desarrollar visor SPA en React 19 + TypeScript + Vite (`web/`) con tipado estricto (`SyncedPlaybackState`, `LyricLine`).
  - [x] Implementar hook `useSyncedLyrics` con auto-reconexión, reloj interpolador local a 60 fps (`performance.now()`) y resolución binaria de versos.
  - [x] Construir componente `KaraokeView` optimizado para TV: tipografía grande (48px+ con glow), auto-scroll vertical suave centrado, atenuación progresiva de versos pasados/futuros y pantalla ambiental con reloj al pausar.
  - [x] Construir `DiagnosticPanel` flotante para pruebas interactivas (controles de mock playback + buscador en vivo de canciones en LRCLIB).
  - [x] Construir suite de tests unitarios e integración en `tests/test_server.py`.
- **Criterios de Aceptación**:
  - WebSocket entrega `SyncedPlaybackState` de inmediato al conectar.
  - Interpolación continua a 60 fps en cliente sin tirones visuales.
  - Auto-scroll suave mantiene el verso activo visible en el tercio central de la pantalla.
  - Suite de pruebas completa (30 tests) pasando exitosamente al 100%.
- **Pruebas Realizadas**:
  - `tests/test_server.py`: Verificación de `/api/status`, endpoints mock `/api/mock/play` y conexión WebSocket inicial.
  - Compilación de producción en Vite (`npm run build`) limpia y sin errores de tipado.
  - FastAPI sirviendo `GET /` devolviendo el `index.html` con status 200.
- **Evidencia**:
  - `pytest -v`: **30 passed in 2.91s** en `tests/`.
  - Servidor FastAPI montando `web/dist` verificado localmente.
- **Riesgos Mitigados**:
  - Validación completa del visor de TV en navegador local antes de lidiar con las complejidades de depuración de Google Cast y Vercel.

---

## 📌 Fase 3 — Integración de Google Cast (Custom Web Receiver)

- **Objetivo**: Convertir la interfaz en un Cast Custom Web Receiver funcional compatible con el SDK v3 de Google Cast e integrar el controlador emisor en el backend Python.
- **Tareas**:
  - [x] Integrar Cast Receiver Framework (`cast_receiver_framework.js`) en `web/index.html`.
  - [x] Configurar el Custom Message Bus con namespace `urn:x-cast:com.alexalyricstv.sync` en `web/src/hooks/useSyncedLyrics.ts`.
  - [x] Implementar arquitectura receptora híbrida universal: sincronización por Cast Channel en Chromecast y por WebSockets en navegador/móvil.
  - [x] Configurar despliegue estático para Vercel con HTTPS (`web/vercel.json`).
  - [x] Implementar controlador backend `src/cast_controller.py` (`LyricsCastController` y `CastManager` con `pychromecast`).
  - [x] Integrar endpoints de control Cast en `src/server.py` (`/api/cast/status`, `/api/cast/devices`, `/api/cast/connect`, `/api/cast/launch`, `/api/cast/disconnect`).
  - [x] Añadir sección interactiva de Chromecast en el `DiagnosticPanel` (búsqueda mDNS, conexión directa por IP, lanzamiento de App ID).
  - [x] Construir suite de pruebas unitarias en `tests/test_cast_controller.py` y `tests/test_server.py`.
- **Criterios de Aceptación**:
  - El Receiver inicializa el contexto CAF v3 al detectar el entorno de Google Cast.
  - El backend se comunica con dispositivos Cast a través del namespace dedicado en el puerto TLS 8009.
  - Compilación de producción en Vite (`npm run build`) limpia y sin errores de tipado.
  - 100% de tests pasando en `pytest` (38 tests).
- **Pruebas Realizadas**:
  - `tests/test_cast_controller.py`: 7 tests para inicialización, recepción de mensajes, envío de payloads JSON, descubrimiento, conexión por IP, lanzamiento y cierre de apps.
  - `tests/test_server.py`: Verificación de endpoints `/api/cast/status` y `/api/cast/disconnect`.
  - `npm run build`: Generación limpia de assets de producción en `web/dist`.
- **Evidencia**:
  - `pytest -v`: **38 passed in 3.39s** en `tests/`.
  - `src/cast_controller.py` y `web/vercel.json` creados y probados.
- **Riesgos Mitigados**:
  - Compatibilidad total sin coste obligatorio: la aplicación funciona tanto en modo Cast nativo (con App ID registrado) como en modo Web local / Tab Cast (a través de WebSockets).

---

## 📌 Fase 4 — Integración End-to-End

- **Objetivo**: Conectar todos los bloques: Detección en Alexa -> LRCLIB -> Motor de Sync -> Emisor Cast -> TV, permitiendo la conmutación entre fuentes de audio y automatizando el ciclo de vida de la pantalla.
- **Tareas**:
  - [x] Implementar `PlaybackOrchestrator` (`src/playback_orchestrator.py`) para coordinar proveedores de audio y automatizar el ciclo de vida de Cast.
  - [x] Implementar `HomeAssistantPlaybackProvider` (`src/hass_provider.py`) para consultar altavoces Echo vía API REST de Home Assistant sin depender de Spotify.
  - [x] Implementar `WebhookPlaybackProvider` (`src/webhook_provider.py`) y endpoint `POST /api/playback/update` para recibir eventos en tiempo real desde cualquier automatización externa.
  - [x] Integrar endpoints de selección de proveedor (`GET/POST /api/playback/provider`) y configuración de AutoCast (`GET/POST /api/autocast/config`) en `src/server.py`.
  - [x] Conectar la salida del orquestador con el bucle de sincronización `background_sync_loop`, replicando las actualizaciones reactivas a WebSockets y Cast.
  - [x] Actualizar `DiagnosticPanel.tsx` con selector visual de fuente de audio, botón de simulación push de Alexa y conmutador de AutoCast.
  - [x] Construir suite de pruebas unitarias e integración en `tests/test_hass_provider.py`, `tests/test_playback_orchestrator.py` y `tests/test_end_to_end.py`.
- **Criterios de Aceptación**:
  - La llegada de un evento de reproducción vía webhook o proveedor actualiza de inmediato el `SyncEngine`, consulta la letra en LRCLIB, calcula la línea activa y la emite a los clientes conectados.
  - El auto-lanzamiento enciende/conecta el Chromecast al iniciar la música y lo cierra tras inactividad prolongada.
  - 100% de la suite de pruebas (49 tests) pasando exitosamente.
- **Pruebas Realizadas**:
  - `tests/test_hass_provider.py`: 3 tests cubriendo estados no autenticado, reposo/apagado y reproducción activa en altavoces Echo.
  - `tests/test_playback_orchestrator.py`: 4 tests validando cambio de proveedor, flujo webhook y ciclo de vida AutoCast (lanzamiento y desconexión por inactividad).
  - `tests/test_end_to_end.py`: 4 tests de integración verificando la cadena completa (selección de proveedor, webhook push con búsqueda de letras, configuración de AutoCast y stream WebSocket).
  - `npm run build`: Compilación de producción de la SPA verificada limpia.
- **Evidencia**:
  - `pytest -v`: **49 passed in 3.53s** en `tests/`.
  - Endpoints `/api/playback/*` y `/api/autocast/*` funcionales y verificados.
- **Riesgos Mitigados**:
  - Independencia total: El sistema puede recibir eventos de Alexa desde Home Assistant, Spotify Connect, o webhooks sin alterar el motor de sincronización ni el visor en TV.

---

## 📌 Fase 5 — Automatización Completa y Ciclo de Vida

- **Objetivo**: Lograr que el sistema no requiera ninguna intervención manual para operar en el día a día, persistiendo preferencias y permitiendo su ejecución como servicio silencioso en Windows.
- **Tareas**:
  - [x] Auto-lanzamiento del Receiver en el Chromecast al detectar `PLAYING`.
  - [x] Manejo automático de pausa (congelar visualización y reloj ambiental en reposo).
  - [x] Detección inmediata de salto de canción y recarga reactiva de letra.
  - [x] Auto-cierre de la sesión de Cast tras inactividad prolongada (180 segundos configurable).
  - [x] Gestor de configuración persistente `ConfigManager` (`src/config_manager.py`) leyendo/escribiendo en `config.json`.
  - [x] Endpoints REST globales de configuración `GET /api/config` y `POST /api/config`.
  - [x] Optimización de latencia en reconexiones Cast mediante caché de IP en memoria (`_device_cache`), evitando los 5 segundos de barrido mDNS.
  - [x] Emisión periódica de PINGs Keep-Alive por el Custom Channel para mantener el socket TLS del Chromecast vivo durante pausas.
  - [x] Scripts de ejecución y daemon para Windows en `scripts/` (`start_daemon.bat`, `start_hidden.vbs`, `stop_daemon.bat`, `install_startup.bat`, `uninstall_startup.bat`).
  - [x] Suite de pruebas automatizadas para configuración y ciclo de vida en `tests/test_config_manager.py` y `tests/test_lifecycle.py`.
- **Criterios de Aceptación**:
  - Experiencia 100% manos libres: el usuario solo interactúa con la voz en Alexa.
  - La TV se activa automáticamente al iniciar la música y vuelve al backdrop tras 3 minutos de silencio.
  - Las configuraciones (dispositivo Cast objetivo, timeout, proveedor por defecto) persisten en `config.json`.
  - El sistema puede arrancar en segundo plano al iniciar Windows sin ventanas de consola visibles.
  - 100% de la suite de pruebas (56 tests) pasando exitosamente.
- **Pruebas Realizadas**:
  - `tests/test_config_manager.py`: 4 tests validando valores por defecto, guardado/recarga en disco, actualizaciones en caliente y endpoints REST `GET/POST /api/config`.
  - `tests/test_lifecycle.py`: 3 tests validando persistencia cruzada de configuración, emisión de keep-alives periódicos y flujo integral de ciclo de vida (Play -> AutoLaunch -> Pause -> Idle Timeout -> AutoQuit).
- **Evidencia**:
  - `pytest -v`: **56 passed in 3.53s** en `tests/`.
  - Scripts en `scripts/` creados y probados.
  - `web/dist` re-compilado en producción en 2.11s.
- **Riesgos Mitigados**:
  - Caídas de socket en Chromecast mitigadas con Keep-Alive periódico cada 15 segundos.
  - Latencia de búsqueda de TV reducida a < 100 ms tras el primer descubrimiento gracias a la caché de IP.

---

## 📌 Fase 6 — Robustez y Recuperación ante Fallos

- **Objetivo**: Garantizar que el sistema tolere cortes de red, canciones sin letra, apagado del Chromecast y desconexiones de Alexa.
- **Tareas**:
  - [ ] Prueba de pérdida temporal de Internet (debe operar con letras en caché).
  - [ ] Prueba con canción sin letra en LRCLIB (debe mostrar carátula y mensaje amigable en TV sin colapsar).
  - [ ] Prueba de Chromecast apagado o fuera de línea (el daemon no debe crashear; reintenta silenciosamente).
  - [ ] Prueba de reinicio imprevisto del daemon (debe reenganchar la sesión activa al arrancar).
- **Criterios de Aceptación**:
  - Ningún error no controlado detiene el servicio.
- **Pruebas**:
  - Matriz de tests de caos y resiliencia.
- **Evidencia**:
  - Registro de logs confirmando recuperación airosa en todos los escenarios.
- **Riesgos**:
  - Bloqueos de socket en `pychromecast`; mitigado con wrappers de reconexión automática.

---

## 📌 Fase 7 — Despliegue y Operación Continua

- **Objetivo**: Dejar el Receiver desplegado en producción (Vercel) y el daemon local configurado como servicio de fondo en Windows.
- **Tareas**:
  - [ ] Desplegar la versión final del Receiver en Vercel con dominio de producción.
  - [ ] Configurar variables de entorno y excluir cualquier secreto del cliente.
  - [ ] Configurar el daemon local de Python para inicio automático o ejecución en segundo plano sin terminal abierta.
  - [ ] Crear manual de usuario breve y comandos de diagnóstico.
- **Criterios de Aceptación**:
  - Sistema operativo de forma permanente y transparente.
- **Pruebas**:
  - Reinicio del PC y verificación de reanudación automática.
- **Evidencia**:
  - URL de Vercel activa y servicio Windows funcionando.
- **Riesgos**:
  - Cambios de IP en la red local; mitigado con descubrimiento por mDNS.

