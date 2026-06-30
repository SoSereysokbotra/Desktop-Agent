"""
Hotkey listener - Global Ctrl+Alt+A hotkey using pynput.
Runs in a daemon thread so it doesn't block the main tray thread.
"""

import threading
import logging

logger = logging.getLogger(__name__)

# The hotkey combination (pynput format)
HOTKEY = "<ctrl>+<alt>+a"


class HotkeyListener:
    def __init__(self, on_activate):
        """
        Args:
            on_activate: Callable with no arguments, called when hotkey fires.
        """
        self._callback = on_activate
        self._listener = None
        self._thread = None

    def start(self):
        """Start listening in a background daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey-listener")
        self._thread.start()
        logger.info(f"Hotkey listener started: {HOTKEY}")

    def stop(self):
        if self._listener:
            self._listener.stop()

    def _run(self):
        try:
            from pynput import keyboard

            # pynput's recommended pattern: create a Listener and pass its
            # canonical() method (bound to the listener instance) into HotKey.
            def for_canonical(f):
                return lambda k: f(listener.canonical(k))

            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse(HOTKEY),
                self._on_hotkey_fired,
            )

            with keyboard.Listener(
                on_press=for_canonical(hotkey.press),
                on_release=for_canonical(hotkey.release),
            ) as listener:
                self._listener = listener
                listener.join()

        except ImportError:
            logger.error("pynput not installed – hotkey unavailable")
        except Exception as e:
            logger.error(f"Hotkey listener error: {e}", exc_info=True)

    def _on_hotkey_fired(self):
        logger.info("Hotkey activated!")
        try:
            self._callback()
        except Exception as e:
            logger.error(f"Hotkey callback error: {e}", exc_info=True)
