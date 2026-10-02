---
name: google-cast-receiver
description: >-
  Guía especializada para el desarrollo, depuración y despliegue de Custom Web Receivers
  de Google Cast utilizando el Cast Application Framework (CAF) v3, gestión de canales
  de mensajería personalizados (Custom Message Bus) y control mediante emisores pychromecast.
license: Apache-2.0
metadata:
  version: v1
  author: jpetersen-dev
---

# Google Cast Custom Web Receiver & CAF v3 Guide

Esta skill proporciona las especificaciones técnicas, patrones de diseño y procedimientos de integración para construir y desplegar **Custom Web Receivers** para dispositivos Google Chromecast.

---

## 1. Fundamentos del Cast Web Receiver SDK (CAF v3)

Un **Custom Web Receiver** es una Single Page Application (HTML5 / CSS / JavaScript) que se ejecuta en el navegador embebido de Google Cast (basado en Chromium) dentro del televisor.

### 1.1. Script Oficial Obligatorio
Debe cargarse en el `<head>` del HTML antes de cualquier script de la aplicación:
```html
<script src="//www.gstatic.com/cast/sdk/libs/caf_receiver/v3/cast_receiver_framework.js"></script>
```

### 1.2. Inicialización Básica
```javascript
const context = cast.framework.CastReceiverContext.getInstance();

// Configuración opcional de opciones del receptor
const options = new cast.framework.CastReceiverOptions();
options.disableIdleTimeout = false;
options.maxInactivity = 180; // 3 minutos de inactividad antes de cerrar

// Iniciar el contexto
context.start(options);
```

---

## 2. Bus de Mensajes Personalizado (Custom Message Bus)

Para intercambiar datos no multimedia directos (como letras de canciones, pulsos de sincronización y estado de metadatos), se utiliza un namespace privado:

### 2.1. Reglas de Namespace
- Formato obligatorio: `urn:x-cast:<identificador_inverso>`
- Ejemplo para este proyecto: `urn:x-cast:com.alexalyricstv.sync`

### 2.2. Recepción de Mensajes en el Receiver
```javascript
const CUSTOM_NAMESPACE = 'urn:x-cast:com.alexalyricstv.sync';

context.addCustomMessageListener(CUSTOM_NAMESPACE, (customEvent) => {
    // customEvent.senderId contiene el ID del emisor (pychromecast)
    // customEvent.data contiene el payload deserializado (JSON)
    const payload = customEvent.data;
    console.log('Mensaje recibido de Cast:', payload);
    
    if (payload.type === 'SYNC_PULSE') {
        window.LyricsApp.handleSyncPulse(payload);
    }
});
```

---

## 3. Emisor Local con Python (`pychromecast`)

El backend local actúa como Cast Sender nativo comunicándose por TLS en el puerto 8009 con el Chromecast:

```python
import pychromecast
from pychromecast.controllers import BaseController

CUSTOM_NAMESPACE = 'urn:x-cast:com.alexalyricstv.sync'

class LyricsCastController(BaseController):
    def __init__(self):
        super().__init__(CUSTOM_NAMESPACE)

    def send_sync(self, payload: dict):
        self.send_message(payload)

# Descubrimiento automático en LAN
chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=["TV Sala", "Chromecast"])
cast = chromecasts[0]
cast.wait()

controller = LyricsCastController()
cast.register_handler(controller)

# Lanzar la aplicación usando el Application ID registrado
cast.start_app("TU_APP_ID")
controller.send_sync({"type": "SYNC_PULSE", "track": "Bohemian Rhapsody"})
```

---

## 4. Requisitos Críticos de Seguridad y Alojamiento
1. **HTTPS Obligatorio**: Google Cast rechaza cualquier Receiver servido por HTTP o con certificados autofirmados inválidos.
2. **Alojamiento Recomendado**: Vercel / Cloudflare Pages proporcionan HTTPS público y despliegue instantáneo.
3. **CORS / Mixed Content**: Al transmitir datos a través del canal nativo Cast (`pychromecast` -> puerto 8009 -> bus CAF), el Receiver no necesita hacer peticiones fetch a la IP local, eliminando cualquier bloqueo de Mixed Content.
