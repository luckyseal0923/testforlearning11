@echo off
cd /d "%~dp0"
start "" http://127.0.0.1:8768/
python server.py
pause
