@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" manage.py seed_neet
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
