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
