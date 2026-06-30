@echo off
REM Desktop Agent - Autostart batch file
REM To make the agent start on Windows boot:
REM   1. Press Win+R, type: shell:startup
REM   2. Copy a shortcut to THIS .bat file into that folder

cd /d "%~dp0"
start "" "venv\Scripts\pythonw.exe" "app.py"
