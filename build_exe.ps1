#Requires -Version 5.0
# Compila src/app.py a un ejecutable (.exe) con PyInstaller.
# Uso: .\build_exe.ps1
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Build .exe: control-acceso-biometrico" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Verificar que exista el venv ---
$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[ERROR] No existe .venv. Corre primero: .\setup.ps1" -ForegroundColor Red
    exit 1
}

# --- 2. Instalar PyInstaller en el venv (version fija) ---
Write-Host "[..] Instalando PyInstaller 6.10.0 ..."
& $venvPython -m pip install --disable-pip-version-check "pyinstaller==6.10.0"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo la instalacion de PyInstaller." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] PyInstaller instalado" -ForegroundColor Green

# --- 3. Asegurar que src/app.py existe ---
if (-not (Test-Path "src\app.py")) {
    Write-Host "[ERROR] No existe src\app.py. Abortando." -ForegroundColor Red
    exit 1
}

# --- 4. Limpiar builds previos ---
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist"  }
if (Test-Path "app.spec") { Remove-Item -Force "app.spec" }

# --- 5. Compilar ---
# --onefile    : un solo .exe
# --name app   : nombre del ejecutable
# --collect-all: fuerza inclusion de data/binaries de DeepFace, TensorFlow,
#                firebase_admin, cv2 (necesario porque usan imports dinamicos)
Write-Host "[..] Compilando (puede tardar 5-15 min) ..."
& $venvPython -m PyInstaller `
    --noconfirm `
    --onefile `
    --name app `
    --collect-all deepface `
    --collect-all firebase_admin `
    --collect-all cv2 `
    --collect-all tensorflow `
    --collect-all retinaface `
    --hidden-import tensorflow `
    --hidden-import tensorflow.python `
    --hidden-import cv2.data `
    src\app.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller fallo. Revisa la salida de arriba." -ForegroundColor Red
    exit 1
}

# --- 6. Copiar config/ y preparar carpeta de distribucion ---
Write-Host "[..] Preparando carpeta dist\app\ ..."
$distDir = "dist\app"
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}
if (Test-Path "dist\app.exe") {
    Move-Item -Force "dist\app.exe" "$distDir\app.exe"
}

# config/settings.json (si existe) y settings.example.json siempre
if (-not (Test-Path "$distDir\config")) {
    New-Item -ItemType Directory -Path "$distDir\config" | Out-Null
}
Copy-Item -Force "config\settings.example.json" "$distDir\config\settings.example.json"
if (Test-Path "config\settings.json") {
    Copy-Item -Force "config\settings.json" "$distDir\config\settings.json"
}
if (Test-Path "config\serviceAccountKey.json") {
    Copy-Item -Force "config\serviceAccountKey.json" "$distDir\config\serviceAccountKey.json"
    Write-Host "[WARN] Se copio serviceAccountKey.json a dist. NO distribuyas ese archivo." -ForegroundColor Yellow
}

# dataset_rostros (vacio, con .gitkeep si existe)
if (-not (Test-Path "$distDir\dataset_rostros")) {
    New-Item -ItemType Directory -Path "$distDir\dataset_rostros" | Out-Null
}

# --- 7. Mensaje final ---
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "[OK] Build completo" -ForegroundColor Green
Write-Host "     Ejecutable: $distDir\app.exe" -ForegroundColor Green
Write-Host ""
Write-Host "     Para distribuir, comprimi la carpeta:" -ForegroundColor Green
Write-Host "       Compress-Archive -Path dist\app -DestinationPath dist\app.zip" -ForegroundColor Green
Write-Host ""
Write-Host "     Notas:" -ForegroundColor Yellow
Write-Host "       - El .exe arranca lento (~10-20s) la primera vez: carga TensorFlow." -ForegroundColor Yellow
Write-Host "       - Si falta config\settings.json, el .exe usa defaults (sync off)." -ForegroundColor Yellow
Write-Host "       - El .exe busca data.db y dataset_rostros\ en su propio directorio." -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""