# 🛡️ Reglas Permanentes del Proyecto — Alexa Lyrics TV

> Ubicación: `.agents/rules/project_rules.md`  
> Ámbito: Políticas de desarrollo, seguridad y control de calidad obligatorias para este proyecto.

---

## 1. Memoria Persistente y Documentación
1. **Actualización Obligatoria**: Cualquier cambio estructural, decisión arquitectónica o avance en las fases debe reflejarse de inmediato en los 4 archivos fundamentales:
   - `ROADMAP.md`: Estados de tareas con checkboxes (`[ ]`, `[~]`, `[x]`) y evidencia.
   - `PROJECT_STATE.json`: Estado operativo, fase actual y dependencias.
   - `DECISIONS.md`: Nuevos Architecture Decision Records (ADRs).
   - `ARCHITECTURE.md`: Diagramas y contratos de interfaces.
2. **Reanudación Estricta**: Si la sesión se reinicia o se pierde contexto, el agente debe leer estos 4 archivos antes de proponer cualquier acción.

---

## 2. Seguridad Estricta
1. **Frontend / Receiver Cero Secretos**: El Custom Web Receiver que se ejecuta en el Chromecast o se aloja en Vercel es código cliente público. **Bajo ninguna circunstancia** contendrá tokens de autenticación de Spotify, credenciales de Amazon, claves API ni secretos.
2. **Canal Cast Seguro**: Los mensajes enviados por el bus de Cast solo contienen información pública de reproducción: artista, canción, duración, letra parseada y estado de transporte.
3. **Variables de Entorno**: Todo secreto requerido por el Daemon local se almacena en `d:\Projects (Local)\alexa-lyrics-tv\.env` (incluido en `.gitignore`).

---

## 3. Control de Calidad y Bloqueo de Avance
1. **Evidencia Requerida**: Queda prohibido marcar una tarea como completada (`[x]`) en el roadmap basándose en "el código parece correcto". Toda tarea completada debe acompañarse de logs, salidas de consola o capturas reales.
2. **Medición Real de Sincronización**: No se declarará exitoso el motor de sincronización sin medir cuantitativamente el desfase (drift) en milisegundos.

---

## 4. Eficiencia de Red (Zero Network Spam)
1. El backend no debe emitir mensajes de estado en bucles infinitos a alta frecuencia (ej. cada 100ms).
2. Se utilizará el modelo de **Interpolación Temporal por Timestamp de Referencia**: el emisor transmite el ancla y el receptor calcula el progreso localmente a 60 fps.
