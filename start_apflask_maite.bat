@echo off
title Apricor Flask - Auto-actualizador de Maite
setlocal
set REPO_URL=https://github.com/federicodiazbobillo/ap-flask.git
set PROJECT_DIR=C:\apricorsoft\ap-flask

echo 🌀 Iniciando verificación de entorno...
if not exist "C:\apricorsoft\" mkdir C:\apricorsoft

:: 1️⃣ Clonar el repositorio si no existe
if not exist "%PROJECT_DIR%\app\" (
    echo 📦 Clonando repositorio desde GitHub...
    git clone %REPO_URL% "%PROJECT_DIR%"
) else (
    echo ✅ Repositorio existente, actualizando...
    cd /d "%PROJECT_DIR%"
    git fetch origin main
    git reset --hard origin/main
)

:: 2️⃣ Crear entorno virtual si no existe
cd /d "%PROJECT_DIR%"
if not exist ".venv\" (
    echo 🔹 Creando entorno virtual...
    python -m venv .venv
)

:: 3️⃣ Activar entorno y actualizar dependencias
echo 🔹 Activando entorno virtual...
call .venv\Scripts\activate

echo 🌀 Actualizando dependencias...
pip install -r requirements.txt --quiet

:: 4️⃣ Ejecutar el servidor Flask
echo 🚀 Iniciando servidor Flask...
python launch.py

echo 🔹 Servidor detenido.
pause
endlocal
