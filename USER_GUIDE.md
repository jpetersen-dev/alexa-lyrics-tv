# 📖 Manual de Operación y Guía de Usuario — Alexa Lyrics TV

Bienvenido a **Alexa Lyrics TV**, el sistema ambiental de sincronización de letras estilo karaoke para televisores no inteligentes mediante **Google Chromecast** o navegadores web locales al reproducir música en altavoces **Amazon Echo / Alexa**.

---

## 🚀 1. Puesta en Marcha Rápida (Windows)

El sistema incluye una suite de scripts en la carpeta [`scripts/`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/scripts) para operar sin necesidad de abrir terminales:

### Opción A: Modo Silencioso en Segundo Plano (Recomendado)
Para que el sistema funcione discretamente sin ventanas de consola abiertas:
1. Haz doble clic en [`scripts/start_hidden.vbs`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/scripts/start_hidden.vbs).
2. El servidor FastAPI, el motor de sincronización y el controlador Cast quedarán activos en segundo plano escuchando en el puerto `8000`.

### Opción B: Iniciar Automáticamente con Windows
Para que el daemon arranque solo cada vez que enciendas tu PC:
1. Haz doble clic en [`scripts/install_startup.bat`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/scripts/install_startup.bat).
2. Se registrará un acceso directo en tu carpeta `shell:startup`.
*(Para desinstalarlo en el futuro, ejecuta [`scripts/uninstall_startup.bat`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/scripts/uninstall_startup.bat)).*

### Opción C: Modo Diagnóstico en Primer Plano
Para ver logs en tiempo real y depurar conexiones:
1. Haz doble clic en [`scripts/start_daemon.bat`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/scripts/start_daemon.bat).
2. Verás la consola con la inicialización del servidor y las transiciones de estado.

### Para Detener el Servicio
- Ejecuta [`scripts/stop_daemon.bat`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/scripts/stop_daemon.bat) para finalizar cualquier proceso activo en el puerto `8000`.

---

## 📱 2. Acceso a la Interfaz Web y Móvil

Puedes acceder a la interfaz desde cualquier dispositivo en tu red local (móvil, tablet, PC o Smart TV):
- **Desde la misma PC**: [http://localhost:8000](http://localhost:8000)
- **Desde el móvil o red local**: `http://192.168.1.88:8000` *(o la IP local de tu PC)*

La interfaz es un **Visor Híbrido Universal**:
- Si se abre en un navegador común (Chrome, Safari, Edge), se conecta automáticamente al WebSocket local (`/ws/playback`).
- Si se ejecuta dentro de un Chromecast, activa el **Cast Application Framework (CAF v3)** y escucha el Custom Channel `urn:x-cast:com.alexalyricstv.sync`.
- Permite hacer clic en cualquier verso para saltar a ese momento de la canción (Seek interactivo).
- Cuenta con un panel desplegable inferior (**Diagnostic Panel**) para cambiar de canción, probar canciones en vivo o buscar letras en LRCLIB.

---

## 📺 3. Modos de Uso con Google Chromecast

### Modo 1: AutoCast Directo (Recomendado)
El daemon detecta cuando empieza la música en Alexa, conecta automáticamente por la red al Chromecast y lanza la pantalla de karaoke:
1. Abre [http://localhost:8000](http://localhost:8000).
2. En el panel de diagnóstico inferior, localiza la sección **Google Chromecast**:
   - Pulsa **Buscar Dispositivos** (escanea por mDNS).
   - O introduce la IP de tu Chromecast (ej: `192.168.1.150`).
3. Activa la casilla **AutoCast (Lanzar y cerrar automáticamente en TV)**.
4. Las preferencias se guardan en `config.json`. Al reproducir música, el TV se encenderá/lanzará solo; tras 3 minutos de pausa o silencio, el TV volverá a su modo reposo/backdrop automáticamente.

### Modo 2: Despliegue en Vercel (Receptor en la Nube con HTTPS)
Para registrar tu propio **Application ID** en la [Google Cast Developer Console](https://cast.google.com/publish) ($5 USD de tarifa única de Google):
1. Importa el repositorio de GitHub [`https://github.com/jpetersen-dev/alexa-lyrics-tv`](https://github.com/jpetersen-dev/alexa-lyrics-tv) en [Vercel](https://vercel.com).
2. El archivo [`vercel.json`](file:///d:/Projects%20%28Local%29/alexa-lyrics-tv/vercel.json) en la raíz compilará automáticamente la aplicación de `web/`.
3. Tu URL de Vercel (ej: `https://alexa-lyrics-tv.vercel.app`) contará con certificado SSL HTTPS válido.
4. En la consola de Google Cast, crea un **Custom Web Receiver** apuntando a esa URL y obtendrás un **App ID** de 8 caracteres.
5. Introduce ese App ID en la configuración (`config.json` o endpoint `/api/config`).

---

## 🎵 4. Fuentes de Reproducción (Playback Providers)

Puedes cambiar la fuente activa en caliente vía el panel web o mediante la API:

| Proveedor | Identificador | Descripción |
| :--- | :--- | :--- |
| **Simulador** | `mock` | Ideal para probar y calibrar sin encender altavoces. Permite cargar canciones de prueba (Queen, etc.). |
| **Webhook HTTP** | `webhook` | Permite enviar el estado de reproducción vía `POST /api/playback/update` desde automatizaciones locales, Node-RED o Alexa Skills. |
| **Home Assistant** | `homeassistant` | Consulta altavoces Echo usando la integración `alexa_media_player` de Home Assistant sin depender de Spotify. |
| **Spotify** | `spotify` | *(Opcional)* Conexión con Spotify Connect Web API. Registrado como `SPOTIFY_POLICY_COMPATIBILITY = UNRESOLVED`. |

### Ejemplo: Enviar Reproducción vía Webhook
```bash
curl -X POST http://localhost:8000/api/playback/update \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Hotel California",
    "artist": "Eagles",
    "duration_ms": 390000,
    "progress_ms": 15000,
    "is_playing": true,
    "device_name": "Echo Dot Living"
  }'
```

---

## ⚙️ 5. Configuración Persistente (`config.json`)

El archivo `config.json` se ubica en la raíz del proyecto. Puedes editarlo a mano o a través de la API REST:

```json
{
  "default_provider": "mock",
  "autocast_enabled": true,
  "target_cast_device": "Living Room TV",
  "target_cast_host": "192.168.1.150",
  "target_cast_app_id": "CC1AD845",
  "idle_timeout_seconds": 180.0,
  "keep_alive_interval_seconds": 15.0,
  "hass_url": "http://homeassistant.local:8123",
  "hass_token": "tu_token_aqui",
  "hass_alexa_entity": "media_player.echo_dot"
}
```

---

## 🛡️ 6. Resiliencia y Solución de Problemas

1. **¿Qué pasa si se corta Internet?**
   - El sistema recurre a la base de datos SQLite local (`lyrics_cache.db`). Todas las canciones reproducidas previamente continuarán sincronizándose con total normalidad.
2. **¿Qué pasa si la canción es instrumental o no tiene letra en LRCLIB?**
   - La pantalla del televisor muestra automáticamente el modo ambiental con la carátula, título, artista y un mensaje amigable ("Pista Instrumental"), sin errores ni colapsos.
3. **¿El televisor se queda encendido para siempre?**
   - No. Si la música se pausa o se detiene durante más de 3 minutos (`idle_timeout_seconds`), el daemon cierra la app de Chromecast y la pantalla regresa al protector de pantalla del televisor.
