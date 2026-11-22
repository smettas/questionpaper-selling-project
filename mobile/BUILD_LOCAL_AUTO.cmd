@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
  "..\.venv\Scripts\python.exe" scripts\build-local-auto.py
) else (
  python scripts\build-local-auto.py
)
exit /b %errorlevel%
