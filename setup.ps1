#Requires -Version 5.0
# Setup del proyecto control-acceso-biometrico.
# Crea estructura, placeholders, venv e instala dependencias fijas.
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Setup: control-acceso-biometrico" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Verificar Python 3.11 ---
$pyExe  = $null
$pyArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $out = & py -3.11 --version 2>&1
    if ($LASTEXITCODE -eq 0 -and "$out" -match "3\.11") {
        $pyExe  = "py"
        $pyArgs = @("-3.11")
    }
}

if (-not $pyExe -and (Get-Command uv -ErrorAction SilentlyContinue)) {
    $found = & uv python find 3.11 2>$null
    if ($LASTEXITCODE -eq 0 -and $found) {
        $out = & $found --version 2>&1
        if ("$out" -match "3\.11") {
            $pyExe  = "$found".Trim()
            $pyArgs = @()
        }
    }
}

if (-not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $out = & python --version 2>&1
    if ($LASTEXITCODE -eq 0 -and "$out" -match "3\.11") {
        $pyExe  = "python"
        $pyArgs = @()
    }
}

if (-not $pyExe) {
    Write-Host "[ERROR] Python 3.11 no detectado." -ForegroundColor Red
    Write-Host "        Instala Python 3.11.x desde https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "        IMPORTANTE: NO uses 3.12 (rompe TensorFlow/DeepFace)." -ForegroundColor Red
    Write-Host "        Marca 'Add python.exe to PATH' durante la instalacion." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Python detectado: $out" -ForegroundColor Green

# --- 2. Estructura de carpetas ---
$dirs = @("src", "config", "docs", "tests", "dataset_rostros")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d | Out-Null
        Write-Host "[..] Creada carpeta: $d"
    }
}
Write-Host "[OK] Estructura de carpetas lista" -ForegroundColor Green

# --- 3. Placeholders src/ ---
"" | Set-Content -Path "src/__init__.py" -Encoding UTF8

@'
"""Acceso a SQLite local (tabla events)."""
pass
'@ | Set-Content -Path "src/db.py" -Encoding UTF8

@'
"""Cliente de Firestore via Admin SDK (sink)."""
pass
'@ | Set-Content -Path "src/firebase_logger.py" -Encoding UTF8

@'
"""Carga de config/settings.json."""
pass
'@ | Set-Content -Path "src/config_loader.py" -Encoding UTF8

@'
"""Deteccion de rostros (Haar/SSD via OpenCV)."""
pass
'@ | Set-Content -Path "src/detector.py" -Encoding UTF8

@'
"""Generacion de embeddings faciales con DeepFace (Facenet512)."""
pass
'@ | Set-Content -Path "src/embeddings.py" -Encoding UTF8

Write-Host "[OK] Placeholders src/ creados" -ForegroundColor Green

# --- 4. config/settings.example.json ---
@'
{
  "sync_enabled": false,
  "firebase_credentials_path": "config/serviceAccountKey.json"
}
'@ | Set-Content -Path "config/settings.example.json" -Encoding ascii
Write-Host "[OK] config/settings.example.json creado" -ForegroundColor Green

# --- 5. .gitkeep ---
New-Item -ItemType File -Force -Path "config/.gitkeep"          | Out-Null
New-Item -ItemType File -Force -Path "tests/.gitkeep"           | Out-Null
New-Item -ItemType File -Force -Path "dataset_rostros/.gitkeep" | Out-Null
Write-Host "[OK] .gitkeep creados (config/ tests/ dataset_rostros/)" -ForegroundColor Green

# --- 6. requirements.txt ---
@'
opencv-python==4.10.0.84
deepface==0.0.93
firebase-admin==6.5.0
numpy==1.26.4
pillow==10.4.0
'@ | Set-Content -Path "requirements.txt" -Encoding ascii
Write-Host "[OK] requirements.txt creado" -ForegroundColor Green

# --- 7. .gitignore ---
@'
__pycache__/
*.pyc
.venv/
venv/
env/
config/serviceAccountKey.json
*.db
*.sqlite
dataset_rostros/*
!dataset_rostros/.gitkeep
temp_*.jpg
dist/
build/
*.spec
.env
config/settings.json
'@ | Set-Content -Path ".gitignore" -Encoding ascii
Write-Host "[OK] .gitignore creado" -ForegroundColor Green

# --- 8. README.md (resumido; el definitivo va aparte) ---
@'
# Control de Acceso Biometrico Facial

Sistema de control de acceso con reconocimiento facial (OpenCV + DeepFace Facenet512), con persistencia local en SQLite y sincronizacion opcional a Firestore.

## Requisitos

- Windows 10/11
- Python **3.11** (NO 3.12, rompe TensorFlow/DeepFace)
- Sin GPU (corre en CPU)

## Instalacion rapida

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```
'@ | Set-Content -Path "README.md" -Encoding UTF8
Write-Host "[OK] README.md creado" -ForegroundColor Green

# --- 9. Entorno virtual e instalacion de dependencias ---
if (-not (Test-Path ".venv")) {
    Write-Host "[..] Creando entorno virtual .venv ..."
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] No se pudo crear el entorno virtual." -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Entorno virtual listo" -ForegroundColor Green

$venvPy = ".\.venv\Scripts\python.exe"
Write-Host "[..] Instalando dependencias (puede tardar varios minutos) ..."
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo la instalacion de dependencias." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dependencias instaladas" -ForegroundColor Green

Write-Host ""
Write-Host "Setup completado. Activa el entorno con:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan