"""
Voice I/O - Microphone input + speaker output
Uses SpeechRecognition (Google Web Speech) for STT and pyttsx3 for TTS.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class VoiceIO:
    def __init__(self):
        self._tts_engine = None
        self._tts_lock = threading.Lock()
        self._sr_available = False
        self._mic_available = False

        # Lazy-init so import errors don't crash at startup
        self._init_tts()
        self._init_sr()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_tts(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Slightly slower rate – sounds more natural
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            self._tts_engine = engine
            logger.info("TTS engine ready")
        except Exception as e:
            logger.warning(f"TTS unavailable: {e}")

    def _init_sr(self):
        try:
            import speech_recognition as sr  # noqa: F401
            self._sr_available = True
            # Lightweight check: just verify PyAudio can see input devices
            import pyaudio
            pa = pyaudio.PyAudio()
            input_devices = sum(
                1 for i in range(pa.get_device_count())
                if pa.get_device_info_by_index(i).get("maxInputChannels", 0) > 0
            )
            pa.terminate()
            if input_devices > 0:
                self._mic_available = True
                logger.info(f"Microphone ready ({input_devices} input device(s) found)")
            else:
                logger.warning("No input audio devices found")
        except ImportError:
            logger.warning("SpeechRecognition or PyAudio not installed")
        except Exception as e:
            logger.warning(f"Mic init failed: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def speak(self, text: str):
        """Convert text to speech (blocking)."""
        if not self._tts_engine:
            print(f"[Agent]: {text}")
            return
        try:
            with self._tts_lock:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"TTS error: {e}")
            print(f"[Agent]: {text}")

    def listen(self, timeout: int = 8, phrase_limit: int = 15) -> str | None:
        """
        Listen from the microphone and return transcribed text.
        Returns None if nothing was heard or an error occurred.
        """
        if not self._sr_available or not self._mic_available:
            logger.warning("Voice input unavailable – showing text dialog")
            return self._ask_text_fallback()

        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 1.0      # wait 1s of silence before stopping
        recognizer.non_speaking_duration = 0.5
        recognizer.dynamic_energy_threshold = True  # auto-adjust to mic level

        try:
            with sr.Microphone() as source:
                logger.info("Calibrating mic for ambient noise (0.3s)...")
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                logger.info(f"Mic calibrated (energy threshold: {recognizer.energy_threshold:.0f}). Speak now!")

                audio = recognizer.listen(
                    source,
                    timeout=timeout,          # seconds to wait for speech to START
                    phrase_time_limit=phrase_limit,  # max recording length
                )

            logger.info("Processing speech...")
            text = recognizer.recognize_google(audio, language="en-US")
            logger.info(f"Heard: {text}")
            return text

        except sr.WaitTimeoutError:
            logger.warning("No speech detected within timeout – did you speak after the notification?")
            return None
        except sr.UnknownValueError:
            logger.warning("Speech was heard but could not be understood")
            return None
        except sr.RequestError as e:
            logger.error(f"Google Speech API error (check internet): {e}")
            return None
        except Exception as e:
            logger.warning(f"Listen error: {e}")
            return None

    @staticmethod
    def _ask_text_fallback() -> str | None:
        """Show a small Tk input dialog when the mic is unavailable."""
        try:
            import tkinter as tk
            import tkinter.simpledialog as sd
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            text = sd.askstring("Desktop Agent – Type Command", "Mic unavailable. Type your command:", parent=root)
            root.destroy()
            return text.strip() if text else None
        except Exception as e:
            logger.warning(f"Text dialog failed: {e}")
            return None

    @property
    def has_voice(self) -> bool:
        return self._sr_available and self._mic_available
