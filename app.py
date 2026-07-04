"""
AI Desktop Agent - Main Entry Point
Version 4: Persistent background assistant
  - System tray icon
  - Global hotkey (Ctrl+Shift+A)
  - Voice input (microphone) + voice output (TTS)
  - Windows toast notifications
  - --cli flag for the original typed-input mode
"""

import os
import sys

# Redirect stdout/stderr to a log file BEFORE importing any third-party libraries
# This prevents crashes under pythonw where sys.stdout and sys.stderr are invalid
log_file = open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log"),
    "a",
    encoding="utf-8",
    buffering=1,
)
sys.stdout = log_file
sys.stderr = log_file

import logging
import threading
import tkinter as tk
import tkinter.simpledialog as sd

from agent.executor import Executor
from agent.memory import Memory
from agent.notifications import notify
from agent.planner import Planner, detect_tools
from agent.voice import VoiceIO
from models.llm import LLM
from models.vision import VisionAnalyzer

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Guard so only one command is processed at a time
_processing_lock = threading.Lock()


class DesktopAgent:
    def __init__(self):
        logger.info("Initializing Desktop Agent...")

        self.llm = LLM()
        self.vision = VisionAnalyzer()
        self.memory = Memory()
        self.planner = Planner(self.llm)
        self.executor = Executor(self.vision)
        self.voice = VoiceIO()

        logger.info("Agent ready!")

    # ------------------------------------------------------------------
    # Core pipeline (unchanged from v3)
    # ------------------------------------------------------------------

    def process_user_input(self, user_input: str) -> str:
        """
        Process a user request, execute tools, return response string.

        This handles both tool execution and conversational responses,
        converting ToolResult objects to strings for voice/notification output.
        """
        logger.info(f"User: {user_input}")
        self.memory.add_interaction("user", user_input)

        # The LLM JSON fallback (~5s) only runs when the regex router finds no
        # match. Show a "Thinking…" toast in that case so voice/tray users see
        # activity during the slow path; fast regex-matched commands stay quiet.
        if not detect_tools(user_input):
            notify("Desktop Agent", "Thinking…", duration=2)

        # Extract tools - may raise ValueError if normalization fails
        # This handles both regex matching AND LLM JSON fallback
        try:
            tools_to_execute = self.planner.extract_tools(user_input)
        except ValueError as e:
            # Normalization failed (e.g. "wait abc" → can't convert to float)
            error_msg = f"I couldn't understand that command: {str(e)}"
            logger.error(f"Tool extraction failed: {e}")
            self.memory.add_interaction("assistant", error_msg)
            return error_msg

        # If no tools needed, generate conversational response
        if not tools_to_execute:
            response = self.planner.generate_response(user_input)
            self.memory.add_interaction("assistant", response)
            return response

        logger.info(f"Tools needed: {tools_to_execute}")

        tool_results = []
        for tool_name, tool_args in tools_to_execute:
            logger.info(f"Executing: {tool_name}({tool_args})")
            notify("Desktop Agent", f"Running: {tool_name}…", duration=2)

            # Execute returns ToolResult object
            result = self.executor.execute(tool_name, tool_args)
            tool_results.append((tool_name, result))

            # Log structured result
            logger.info(f"Result: status={result.status}, message={result.result}")

        response = self.planner.generate_response_with_context(user_input, tool_results)
        self.memory.add_interaction("assistant", response)
        return response

    # ------------------------------------------------------------------
    # Tray callbacks – each runs on its own daemon thread
    # ------------------------------------------------------------------

    def handle_voice_command(self):
        """Activated by hotkey or tray 'Talk to Agent'."""
        if not _processing_lock.acquire(blocking=False):
            notify("Desktop Agent", "Already processing a command, please wait.")
            return
        try:
            notify("Desktop Agent", "Listening… speak your command")
            text = self.voice.listen()
            if not text:
                notify("Desktop Agent", "Didn't catch that – try again.")
                return
            notify("Desktop Agent", f'You said: "{text}"')

            response = self.process_user_input(text)
            notify("Desktop Agent", response[:100])
            self.voice.speak(response)
        finally:
            _processing_lock.release()

    def handle_type_command(self):
        """Activated by tray 'Type a Command' – shows a small input dialog."""
        if not _processing_lock.acquire(blocking=False):
            notify("Desktop Agent", "Already processing a command, please wait.")
            return
        try:
            # Run the Tk dialog on the main thread via a simple approach
            text = self._ask_text_dialog()
            if not text:
                return
            response = self.process_user_input(text)
            notify("Desktop Agent", response[:100])
            self.voice.speak(response)
        finally:
            _processing_lock.release()

    def handle_quit(self):
        logger.info("Agent shutting down")
        notify("Desktop Agent", "Shutting down…", duration=2)

    # ------------------------------------------------------------------
    # Small Tk input dialog
    # ------------------------------------------------------------------

    @staticmethod
    def _ask_text_dialog() -> str | None:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        text = sd.askstring(
            "Desktop Agent",
            "Enter your command:",
            parent=root,
        )
        root.destroy()
        return text.strip() if text else None

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def run_tray(self):
        """
        Persistent mode: system tray + global hotkey.
        Blocks on the main thread (required by pystray on Windows).
        """
        from agent.hotkey import HotkeyListener
        from agent.tray import TrayIcon

        # Start hotkey listener
        hotkey = HotkeyListener(on_activate=self.handle_voice_command)
        hotkey.start()

        # Build tray and block
        tray = TrayIcon(
            on_voice=self.handle_voice_command,
            on_type=self.handle_type_command,
            on_quit=self.handle_quit,
        )

        notify(
            "Desktop Agent",
            "Agent is running! Press Ctrl+Shift+A to speak a command.",
        )

        try:
            tray.run()  # blocks until quit
        finally:
            hotkey.stop()

    def run_cli(self):
        """Original interactive CLI mode (for development / debugging)."""
        print("=" * 50)
        print("Desktop Agent v4 – CLI Mode")
        print("=" * 50)
        print("\nExamples:")
        print("  'Open Chrome'")
        print("  'Take a screenshot'")
        print("  'What do I have open?'")
        print("  'Type hello in notepad'")
        print("\nType 'quit' to exit\n")

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit"):
                    print("Goodbye!")
                    break

                response = self.process_user_input(user_input)
                print(f"Agent: {response}\n")

            except KeyboardInterrupt:
                print("\nInterrupted. Type 'quit' to exit.")
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                print(f"Error: {e}\n")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cli_mode = "--cli" in sys.argv
    agent = DesktopAgent()

    if cli_mode:
        agent.run_cli()
    else:
        agent.run_tray()
