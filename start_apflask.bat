@echo off
cd /d C:\apricor-installer
call env\Scripts\activate.bat
python ap-flask\launch.py
