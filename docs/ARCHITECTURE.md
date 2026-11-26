# Arquitectura

## Flujo

```
[Camara] -> [Detector (Haar/SSD)] -> [Embedder (Facenet512)] -> [Matcher (cosine)]
                                                                      |
                                                                      v
                                                              [SQLite events]
                                                                      |
                                                                      v
                                                           [Sync -> Firestore]
```

## Decisiones

### SQLite es fuente de verdad, Firestore es sink

- **SQLite es local, rapido, sin red, siempre disponible.** Si Firestore falla o no hay internet, no se pierden eventos: se escriben local y listo.
- **Firestore es sink**: recibe una copia asincrona via Admin SDK para consulta remota desde la consola. No se lee desde ahi en runtime.
- Esto evita que el flujo de control de acceso dependa de la nube.

### Admin SDK directo, no Cloud Functions

- **El plan Spark (gratis) no permite Cloud Functions** de forma sostenida.
- Cloud Functions agrega latencia, cold starts y un pipeline de deploy que no aporta nada a una tarea escolar.
- El Admin SDK en el script es una dependencia y listo: escritura directa a Firestore desde el mismo proceso que ya escribe SQLite.

## Deuda tecnica explicita

- **Credencial de larga vida en disco**: `serviceAccountKey.json` no expira. Si se filtra, hay que rotarla manualmente desde la consola de Firebase. Aceptable para tarea escolar; no para produccion.
- **Sin cifrado en reposo**: SQLite plano. Cualquiera con acceso al disco lee los eventos.
- **Sin reglas deny-all en Firestore**: el Admin SDK las ignora igual. Aceptable aca porque solo el script (server-side) escribe; no hay SDK cliente.
- **Sin anti-spoofing**: el detector acepta fotos impresas o pantallas. Fase 2 podria sumar liveness detection.
- **Sync sin reintentos ni cola local**: si Firestore falla al escribir un evento, se pierde esa copia remota (la local queda). Fase 2: outbox pattern.
- **Sin tests unitarios**: solo smoke test de integracion.