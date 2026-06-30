"""
System tray icon using pystray + Pillow.
Must run on the main thread (Windows requirement).
"""

import threading
import logging
import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

ICON_SIZE = 64
ICON_COLOR = (99, 102, 241)   # Indigo
ICON_BG    = (17,  24,  39)   # Dark background


def _make_icon_image() -> Image.Image:
    """Create a simple circular icon programmatically."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled circle
    draw.ellipse([4, 4, ICON_SIZE - 4, ICON_SIZE - 4], fill=ICON_COLOR)
    # Small white dot in centre to suggest an "eye" / listening state
    cx = ICON_SIZE // 2
    draw.ellipse([cx - 6, cx - 6, cx + 6, cx + 6], fill=(255, 255, 255, 220))
    return img


class TrayIcon:
    def __init__(self, on_voice, on_type, on_quit):
        """
        Args:
            on_voice : Called when user picks "Talk to Agent"
            on_type  : Called when user picks "Type a Command"
            on_quit  : Called when user picks "Quit"
        """
        self._on_voice = on_voice
        self._on_type  = on_type
        self._on_quit  = on_quit
        self._icon     = None

    def run(self):
        """
        Build and run the tray icon on the calling thread (must be main thread).
        Blocks until the icon is stopped.
        """
        try:
            icon_image = _make_icon_image()

            menu = pystray.Menu(
                pystray.MenuItem("🎤  Talk to Agent (Ctrl+Shift+A)", self._handle_voice, default=True),
                pystray.MenuItem("⌨️  Type a Command",              self._handle_type),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("✖  Quit",                         self._handle_quit),
            )

            self._icon = pystray.Icon(
                name="DesktopAgent",
                icon=icon_image,
                title="Desktop Agent",
                menu=menu,
            )

            logger.info("System tray icon running")
            self._icon.run()

        except ImportError:
            logger.error("pystray not installed – tray unavailable. Run in CLI mode instead.")
            raise

    def stop(self):
        if self._icon:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Internal handlers (called on the pystray thread)
    # ------------------------------------------------------------------

    def _handle_voice(self, icon, item):
        threading.Thread(target=self._on_voice, daemon=True, name="agent-voice").start()

    def _handle_type(self, icon, item):
        threading.Thread(target=self._on_type, daemon=True, name="agent-type").start()

    def _handle_quit(self, icon, item):
        self._on_quit()
        icon.stop()
