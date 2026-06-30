"""
start_agent.pyw - Silent launcher (no console window).
Run this file directly or point Task Scheduler / Startup folder at it.
"""
import subprocess
import sys
import os

# Resolve paths relative to this file's location
here = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(here, "venv", "Scripts", "pythonw.exe")
app_script  = os.path.join(here, "app.py")

# Fall back to the current interpreter if venv pythonw doesn't exist
if not os.path.exists(venv_python):
    venv_python = sys.executable.replace("python.exe", "pythonw.exe")

subprocess.Popen(
    [venv_python, app_script],
    cwd=here,
    close_fds=True,
)
