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

- **Objetivo**: Crear un módulo independiente que reciba artista + canción, consulte LRCLIB, normalice títulos, maneje errores y almacene en caché local.
- **Tareas**:
  - [ ] Crear el módulo normalizador de títulos (`clean_track_title`).
  - [ ] Implementar cliente HTTP asíncrono para LRCLIB con timeouts y reintentos.
  - [ ] Implementar el parser de formato LRC a estructuras numéricas `{ time_ms, text }`.
  - [ ] Diseñar la base de datos SQLite para caché persistente de letras.
  - [ ] Manejar casos de canciones sin letra sincronizada (fallback a letra estática o aviso en UI).
- **Criterios de Aceptación**:
  - Canción conocida devuelve array ordenado por `time_ms`.
  - Canciones con títulos complejos (ej. `Song - Remastered 2011`) se limpian y resuelven correctamente.
  - Consulta repetida se resuelve desde la base de datos local en menos de 5 ms.
- **Pruebas**:
  - Suite de tests unitarios con 10 canciones de prueba variadas (con letra sincronizada, solo instrumental, y sin letra).
- **Evidencia**:
  - Reporte de tests con tiempos de respuesta de caché vs red.
- **Riesgos**:
  - Rate limiting de LRCLIB; mitigado con la caché SQLite local.

---

## 📌 Fase 3 — Motor de Sincronización Temporal

- **Objetivo**: Diseñar y verificar el algoritmo matemático de interpolación temporal para garantizar visualización sincronizada sin saturar la red.
- **Tareas**:
  - [ ] Implementar generador de paquetes `SYNC_PULSE` con `reference_timestamp`.
  - [ ] Desarrollar la función de cálculo de posición local del cliente (`requestAnimationFrame` math).
  - [ ] Implementar algoritmo de suavizado (LERP) para transiciones sin saltos bruscos.
  - [ ] Medir el error práctico (drift) entre el tiempo real del audio y el tiempo calculado.
- **Criterios de Aceptación**:
  - Desfase visual medido inferior a 1 segundo en todo momento.
  - Comportamiento consistente ante pausas y saltos de posición (seek).
- **Pruebas**:
  - Simulación de playback de 3 minutos midiendo deriva temporal acumulada.
- **Evidencia**:
  - Gráfico o métrica registrada de deriva milisegundo a milisegundo.
- **Riesgos**:
  - Desincronización del reloj del sistema entre emisor y receptor; mitigado calculando deltas locales.

---

## 📌 Fase 4 — Interfaz Local para TV (Web/React)

- **Objetivo**: Construir la interfaz de usuario de pantalla completa, optimizada exclusivamente para pantallas de TV a 1080p y 4K.
- **Tareas**:
  - [ ] Configurar layout oscuro minimalista con alto contraste (estilo karaoke ambiental).
  - [ ] Implementar tipografía legible a 3 metros de distancia (fuente destacada, 48px+).
  - [ ] Desarrollar scroll vertical automático centrado en la línea activa.
  - [ ] Agregar animaciones suaves de transición entre versos.
  - [ ] Diseñar estados de espera: Inactivo / Buscando letra / Canción instrumental / Pausado.
  - [ ] Validar funcionamiento completo en navegador antes de conectar con Cast.
- **Criterios de Aceptación**:
  - Visualización impecable en resolución 1920x1080.
  - La línea actual resalta con brillo/color distintivo y scroll sin tirones (60 fps).
- **Pruebas**:
  - Ejecución en navegador local simulando diferentes canciones y cambios de ritmo.
- **Evidencia**:
  - Capturas de pantalla y test interactivo en navegador.
- **Riesgos**:
  - Rendimiento gráfico en el hardware limitado del Chromecast; mitigado utilizando CSS puro (`transform: translateY` acelerado por GPU).

---

## 📌 Fase 5 — Integración de Google Cast (Custom Web Receiver)

- **Objetivo**: Convertir la interfaz en un Cast Custom Web Receiver funcional compatible con el SDK v3 de Google Cast.
- **Tareas**:
  - [ ] Integrar Cast Receiver Framework (`cast_receiver_framework.js`).
  - [ ] Configurar el Custom Message Bus con namespace `urn:x-cast:com.alexalyricstv.sync`.
  - [ ] Configurar despliegue en Vercel con HTTPS.
  - [ ] Registrar la aplicación en Google Cast Developer Console o configurar modo desarrollo.
  - [ ] Probar recepción de mensajes desde emisor de prueba.
- **Criterios de Aceptación**:
  - El Receiver carga en el Chromecast real y responde a mensajes JSON enviados por el canal Cast.
- **Pruebas**:
  - Envío manual de paquetes de prueba desde script emisor al Chromecast físico en la TV.
- **Evidencia**:
  - Receiver corriendo en la pantalla del televisor.
- **Riesgos**:
  - Requisito de $5 USD para Google Cast Developer Console; se ofrece alternativa de pruebas directas en navegador o Cast local.

---

## 📌 Fase 6 — Integración End-to-End

- **Objetivo**: Conectar todos los bloques: Detección en Alexa -> LRCLIB -> Motor de Sync -> Emisor Cast -> TV.
- **Tareas**:
  - [ ] Unificar el Daemon local que escucha la reproducción y orquesta el flujo.
  - [ ] Conectar la salida del observador con el motor de letras.
  - [ ] Conectar la letra parseada con el canal de Cast.
  - [ ] Verificar la cadena completa con canciones reales reproducidas en el Echo.
- **Criterios de Aceptación**:
  - Al sonar una canción en Alexa, la TV muestra la letra correspondiente de forma automática.
- **Pruebas**:
  - Prueba en vivo con 5 canciones consecutivas.
- **Evidencia**:
  - Video o reporte de sesión completa con timestamps correlacionados.
- **Riesgos**:
  - Caída de la conexión Cast por timeout; mitigado con mecanismo de keep-alive.

---

## 📌 Fase 7 — Automatización Completa y Ciclo de Vida

- **Objetivo**: Lograr que el sistema no requiera ninguna intervención manual para operar en el día a día.
- **Tareas**:
  - [ ] Auto-lanzamiento del Receiver en el Chromecast al detectar `PLAYING`.
  - [ ] Manejo automático de pausa (congelar visualización).
  - [ ] Detección inmediata de salto de canción y recarga de letra.
  - [ ] Auto-cierre de la sesión de Cast tras 3 minutos de inactividad continuada.
- **Criterios de Aceptación**:
  - Experiencia 100% manos libres: el usuario solo interactúa con la voz en Alexa.
- **Pruebas**:
  - Ciclo de prueba: Reproducir -> Pausar -> Esperar timeout -> Verificar que la TV se apaga/vuelve al backdrop.
- **Evidencia**:
  - Logs de transición de estados de ciclo de vida.
- **Riesgos**:
  - Retardo en el lanzamiento de la app en Chromecast; optimizado pre-cargando la letra en paralelo al lanzamiento.

---

## 📌 Fase 8 — Robustez y Recuperación ante Fallos

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

## 📌 Fase 9 — Despliegue y Operación Continua

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
