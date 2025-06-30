@echo off
cd /d C:\apricor-installer
call env\Scripts\activate.bat

echo Verificando e instalando dependencias...
pip install -r ap-flask\requirements.txt

echo Iniciando aplicación...
python ap-flask\launch_dev.py
