@echo off
REM Launch Whispr silently using the bundled virtual environment.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" run.py
