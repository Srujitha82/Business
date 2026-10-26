@echo off
REM ShopPulse: Python only (no Node.js needed). Double-click this file.
cd /d "%~dp0"
python -m pip install -r backend\requirements.txt
start "" http://127.0.0.1:5050
python backend\app.py
pause
