"""
Notifications - Native Windows toast notifications via PowerShell.
No extra Python library required.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def notify(title: str, message: str, duration: int = 5):
    """
    Show a Windows toast notification.
    Uses PowerShell's BurntToast-style notification via the .NET API.
    Falls back to a simple print if PowerShell is unavailable.
    """
    ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$notify.BalloonTipTitle = "{title}"
$notify.BalloonTipText = "{message}"
$notify.Visible = $True
$notify.ShowBalloonTip({duration * 1000})
Start-Sleep -Milliseconds {duration * 1000 + 500}
$notify.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        logger.warning(f"Notification failed: {e}")
        print(f"[{title}] {message}")
