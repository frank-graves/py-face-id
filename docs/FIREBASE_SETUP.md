# Configuracion de Firebase (Firestore)

Guia minima para conectar el proyecto a Firestore con plan Spark (gratis) usando el Admin SDK desde Python.

## 1. Cuenta Google

Si no tenes, creala en https://accounts.google.com.

## 2. Crear proyecto en Firebase

1. Anda a https://console.firebase.google.com
2. Click en **"Agregar proyecto"**.
3. Nombre del proyecto (ej: `control-acceso-biometrico`).
4. **Desactivar** Google Analytics.
5. Click en **"Crear proyecto"** y espera a que termine.

## 3. Crear base de datos Firestore

1. Menu lateral: **Build → Firestore Database**.
2. Click en **"Crear base de datos"**.
3. Modo: **Produccion**.
4. Ubicacion: `us-central1` (o la mas cercana disponible en tier gratis).
5. Click en **"Habilitar"**.

## 4. Generar cuenta de servicio

1. Click en el engranaje (⚙) arriba a la izquierda → **"Configuracion del proyecto"**.
2. Pestaña **"Cuentas de servicio"**.
3. Click en **"Generar nueva clave privada"** → confirmar.
4. Se descarga un `.json`. Renombralo a `serviceAccountKey.json`.

## 5. Colocar el JSON en el proyecto

Mover el archivo descargado a:

```
config/serviceAccountKey.json
```

## 6. Copiar settings de ejemplo

```powershell
Copy-Item config/settings.example.json config/settings.json
```

Verificar que `firebase_credentials_path` apunta a `config/serviceAccountKey.json`.

## 7. Verificar conexion

```powershell
.\.venv\Scripts\python.exe -m src.smoke_test
```

Si todo esta bien debe imprimir: `Firestore: OK`.

## 8. Verificar en la consola web

Firestore → Data → deberia aparecer la coleccion `smoke_tests` con el documento `smoke_test_latest` tras correr el smoke test.

## ADVERTENCIA

**Nunca commitees** `config/serviceAccountKey.json`. Ya esta en `.gitignore`. Ese archivo da acceso total al proyecto Firebase: si se filtra, hay que rotarlo manualmente desde la consola.