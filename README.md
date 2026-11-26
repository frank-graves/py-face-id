# Control de Acceso Biometrico Facial

Sistema de control de acceso con reconocimiento facial (OpenCV + DeepFace Facenet512), con persistencia local en SQLite como fuente de verdad y sincronizacion opcional a Firestore como sink.

## Requisitos

- Windows 10/11
- Python **3.11** (NO 3.12, rompe TensorFlow/DeepFace)
- Sin GPU (corre en CPU)

## Instalacion (resumen)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

Eso crea carpetas, placeholders, `.venv` e instala dependencias fijas.

Pasos siguientes:

1. Configurar Firebase, ver `docs/FIREBASE_SETUP.md`.
2. Copiar `config/settings.example.json` a `config/settings.json` y ajustar.
3. Verificar entorno: `.\.venv\Scripts\python.exe -m src.smoke_test`.

## Estructura

```
control-acceso-biometrico/
+-- config/                 # settings.json + serviceAccountKey.json (gitignored)
+-- dataset_rostros/        # imagenes para enrolamiento
+-- docs/                   # FIREBASE_SETUP.md, ARCHITECTURE.md
+-- src/
|   +-- __init__.py
|   +-- config_loader.py
|   +-- db.py
|   +-- detector.py
|   +-- embeddings.py
|   +-- firebase_logger.py
|   +-- smoke_test.py
+-- tests/
+-- requirements.txt
+-- setup.ps1
+-- .gitignore
+-- README.md
```

## Limitaciones conocidas / Deuda tecnica

- `serviceAccountKey.json` de larga vida en disco (rotar manualmente si se filtra).
- SQLite sin cifrar en reposo.
- Sin anti-spoofing (una foto puede engañar al detector).
- Sin reglas deny-all en Firestore (el Admin SDK las ignora igual).
- Sync a Firestore sin reintentos ni cola local.
- Solo smoke test, sin tests unitarios.
- Sin empaquetado (.exe): se corre con el Python del venv.