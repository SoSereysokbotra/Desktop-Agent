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

import requests

from agent.executor import Executor
from agent.memory import Memory
from agent.notifications import notify
from agent.orchestrator import DONE_TOOL, PARSE_ERROR_MARKER, ReActOrchestrator
from agent.planner import (
    Planner,
    count_distinct_actions,
    detect_tools,
    has_word_marker,
)
from agent.tools import ToolResult
from agent.voice import VoiceIO
from models.llm import LLM, OLLAMA_URL, USE_OLLAMA
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


class GatedExecutor:
    """
    Executor wrapper that routes the orchestrator's Act step through the SAME
    safety confirmation gate as the single-shot fallback path, and fires a
    per-action "Running: tool" toast for UI consistency.

    Every orchestrator action is LLM-guessed (there is no regex "trusted" path
    inside the loop), so every impactful action is gated. Because the
    orchestrator can only execute THROUGH this wrapper, the gate is
    architecturally unbypassable via the orchestrator - it is not merely
    applied by convention in the caller.
    """

    def __init__(self, real_executor, confirm_fn, describe_fn, impactful_tools,
                 on_run=None):
        self._exec = real_executor
        self._confirm = confirm_fn
        self._describe = describe_fn
        self._impactful = impactful_tools
        self._on_run = on_run

    def execute(self, tool_name, args=None):
        if self._on_run:
            self._on_run(tool_name)
        if tool_name in self._impactful:
            logger.warning(
                f"[safety] orchestrator impactful action needs confirmation: "
                f"{tool_name}({args})"
            )
            if not self._confirm(self._describe(tool_name, args or {})):
                logger.warning(
                    f"[safety] DENIED (orchestrator step, not executed): "
                    f"{tool_name}({args})"
                )
                # user_denied=True tells the orchestrator to ABORT the whole
                # task immediately instead of retrying the denied action.
                return ToolResult.error(
                    "Action not confirmed by user - task stopped",
                    data={"user_denied": True, "tool": tool_name, "args": args},
                )
            logger.info(
                f"[safety] CONFIRMED by user (orchestrator step): {tool_name}"
            )
        return self._exec.execute(tool_name, args)


class DesktopAgent:
    def __init__(self):
        logger.info("Initializing Desktop Agent...")

        self.llm = LLM()
        self.vision = VisionAnalyzer()
        self.memory = Memory()
        self.planner = Planner(self.llm)
        self.executor = Executor(self.vision)
        self.voice = VoiceIO()

        # GUI objects - created on the main thread inside run(). None in CLI mode.
        self.bridge = None
        self.panel = None

        # Warn immediately if the Ollama backend isn't reachable, rather than
        # letting the user discover it only when their first command fails.
        self._check_ollama_health()

        logger.info("Agent ready!")

    def _check_ollama_health(self):
        """
        Ping the Ollama API once at startup. If it's down, log and raise a
        toast right away so the user knows commands will fail until the
        server is running. No-op when the transformers backend is in use.
        """
        if not USE_OLLAMA:
            return

        # OLLAMA_URL is the /api/generate endpoint; derive the /api/tags probe.
        base = OLLAMA_URL.rsplit("/api/", 1)[0]
        tags_url = f"{base}/api/tags"
        try:
            resp = requests.get(tags_url, timeout=3)
            resp.raise_for_status()
            logger.info("Ollama health check OK at startup")
        except Exception as e:
            logger.error(
                f"Ollama health check FAILED at startup "
                f"[{type(e).__name__}]: {e}"
            )
            notify(
                "Desktop Agent",
                "Ollama server not reachable - is it running? "
                "Commands will fail until it starts.",
                duration=6,
            )

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

        # DECISION PATH LOGGING -------------------------------------------------
        # regex_hits non-empty  -> deterministic, trusted path (no LLM guess).
        # regex_hits empty      -> the LLM JSON fallback decides; anything it
        #                          produces is UNTRUSTED and impactful actions
        #                          from it must be confirmed before executing.
        regex_hits = detect_tools(user_input)
        from_fallback = not regex_hits
        logger.info(f"[decision] input={user_input!r} regex_hits={regex_hits} "
                    f"from_fallback={from_fallback}")

        # "Thinking…" toast only on the slow fallback path (exactly once).
        if from_fallback:
            notify("Desktop Agent", "Thinking…", duration=2)

        # Extract tools - may raise ValueError if normalization fails
        try:
            tools_to_execute = self.planner.extract_tools(user_input)
        except ValueError as e:
            error_msg = f"I couldn't understand that command: {str(e)}"
            logger.error(f"Tool extraction failed: {e}")
            self.memory.add_interaction("assistant", error_msg)
            return error_msg

        logger.info(f"[decision] tools_to_execute={tools_to_execute}")

        # If no tools needed, generate conversational response
        if not tools_to_execute:
            logger.info("[decision] no tool -> conversational response")
            response = self.planner.generate_response(user_input)
            self.memory.add_interaction("assistant", response)
            return response

        # COMPOUND-COMMAND DETECTION -----------------------------------------
        # A single command can regex-match ONE tool yet contain multiple
        # distinct intents. e.g. "open notepad and take a screenshot" regex-
        # matches only take_screenshot (rule order), so the single-shot path
        # would silently DROP "open notepad" - a partial-completion bug in the
        # same danger class as the earlier hallucination bug.
        #
        # Detect it with TWO independent signals that must BOTH agree:
        #   (1) >=2 DISTINCT tool actions are detectable in the text, AND
        #   (2) a WORD connective (and/then/after/next/also/followed by) is
        #       present (never commas/semicolons - those appear in coordinates
        #       like "100,200" and in typed content).
        # Requiring BOTH keeps a literal action word inside typed content
        # ("type click here", "type open the door") single-shot: two actions
        # are detected but there is no connective, so is_compound stays False.
        #
        # This OVERRIDES the regex short-circuit and is deliberately NOT gated
        # on from_fallback - a clean regex hit no longer masks a compound
        # command. (Supersedes the weaker from_fallback-gated marker heuristic
        # from commit 440f9f8.)
        distinct_actions = count_distinct_actions(user_input)
        word_marker = has_word_marker(user_input)
        is_compound = distinct_actions >= 2 and word_marker
        logger.info(
            f"[decision] compound_check distinct_actions={distinct_actions} "
            f"word_marker={word_marker} is_compound={is_compound}"
        )

        # Route genuine multi-step goals to the ReAct orchestrator, which
        # OBSERVES each result and adapts/self-corrects between steps, instead
        # of blindly running a guessed batch. Two triggers:
        #   - is_compound: a compound command (works even on a regex hit), OR
        #   - the LLM fallback classifier explicitly returned a >=2 array.
        if is_compound or (from_fallback and len(tools_to_execute) >= 2):
            logger.info(
                f"[decision] multi-step goal -> ReAct orchestrator "
                f"(is_compound={is_compound}, from_fallback={from_fallback}, "
                f"classifier_tools={len(tools_to_execute)})"
            )
            return self._run_orchestrated(user_input)

        tool_results = []
        for tool_name, tool_args in tools_to_execute:
            # SAFETY GATE: an impactful action (types/opens into the focused
            # window) that came from the LLM fallback (not a clear regex match)
            # must be confirmed by the user before it runs. This closes the
            # hallucinated-tool-call risk (old Phase 6 confirmation layer).
            if from_fallback and tool_name in self.IMPACTFUL_TOOLS:
                logger.warning(
                    f"[safety] fallback impactful action needs confirmation: "
                    f"{tool_name}({tool_args})"
                )
                if not self._confirm_action(self._describe_action(tool_name, tool_args)):
                    logger.warning(f"[safety] DENIED (not executed): {tool_name}({tool_args})")
                    tool_results.append((
                        tool_name,
                        ToolResult.error(
                            "Action not confirmed by user - skipped for safety",
                            data={"tool": tool_name, "args": tool_args},
                        ),
                    ))
                    continue
                logger.info(f"[safety] CONFIRMED by user: {tool_name}")

            logger.info(f"Executing: {tool_name}({tool_args})")
            notify("Desktop Agent", f"Running: {tool_name}…", duration=2)

            result = self.executor.execute(tool_name, tool_args)
            tool_results.append((tool_name, result))
            logger.info(f"Result: status={result.status}, message={result.result}")

        response = self.planner.generate_response_with_context(user_input, tool_results)
        self.memory.add_interaction("assistant", response)
        return response

    def _run_orchestrated(self, user_input: str) -> str:
        """
        Run a multi-step goal through the ReAct orchestrator (Think->Act->
        Observe). Built PER COMMAND (fresh task_id, no stale bridge/state).

        Actions execute through a GatedExecutor, so the SAME safety gate as the
        single-shot path applies to every impactful step - the orchestrator has
        no way around it. The "Thinking…" toast already fired in
        process_user_input; per-action "Running: tool" toasts come from the
        GatedExecutor. task_steps logging happens inside the orchestrator via
        the real self.memory.
        """
        gated = GatedExecutor(
            self.executor,
            self._confirm_action,
            self._describe_action,
            self.IMPACTFUL_TOOLS,
            on_run=lambda t: notify("Desktop Agent", f"Running: {t}…", duration=2),
        )
        # Per-command construction (max_steps + loop logic unchanged from Phase 2).
        orchestrator = ReActOrchestrator(self.llm, gated, self.memory)
        summary = orchestrator.run(user_input)
        logger.info(
            f"[decision] orchestrator done: status={summary['status']} "
            f"actions={summary['actions_taken']} iterations={summary['iterations']} "
            f"elapsed={summary['elapsed_sec']}s reason={summary['reason']!r}"
        )

        # Summarize the run for the user in the System persona, feeding the real
        # per-step observations as context (skipping the done/parse-error markers).
        tool_results = [
            (e["tool"], f"[{e['status']}] {e['observation']}")
            for e in summary["trace"]
            if e["tool"] not in (DONE_TOOL, PARSE_ERROR_MARKER)
        ]
        response = self.planner.generate_response_with_context(user_input, tool_results)
        self.memory.add_interaction("assistant", response)
        return response

    # Impactful actions that must be confirmed when they come from the LLM
    # fallback rather than a clear, deterministic regex match.
    IMPACTFUL_TOOLS = {"type_text", "open_app"}

    @staticmethod
    def _describe_action(tool_name: str, tool_args: dict) -> str:
        if tool_name == "type_text":
            return (
                "The agent wants to TYPE this into your currently focused window:\n\n"
                f"“{tool_args.get('text', '')}”"
            )
        if tool_name == "open_app":
            return f"The agent wants to OPEN the application: {tool_args.get('app_name', '')}"
        return f"The agent wants to run {tool_name} with args {tool_args}"

    def _confirm_action(self, description: str) -> bool:
        """
        Ask the user to approve an impactful action. Returns True only on an
        explicit YES. Defaults to DENY on timeout or if no channel exists.
        GUI mode -> modal dialog on the GUI thread; CLI mode -> console prompt.
        """
        if self.bridge is not None:
            done = threading.Event()
            holder = {"ok": False}
            self.bridge.confirm_requested.emit(
                {"text": description, "event": done, "result": holder}
            )
            if not done.wait(timeout=120):
                logger.warning("[safety] confirmation timed out -> DENY")
                return False
            return holder["ok"]

        # No GUI (CLI/dev): ask on the console; deny if that's not possible.
        try:
            ans = input(f"\n[CONFIRM] {description}\nAllow this action? (y/N): ")
            return ans.strip().lower() in ("y", "yes")
        except Exception:
            logger.warning("[safety] no confirmation channel -> DENY")
            return False

    def _on_confirm_requested(self, payload: dict):
        """GUI-thread slot: show a modal Yes/No and report the result back."""
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self.panel)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Desktop Agent — confirm action")
        box.setText(payload["text"])
        box.setInformativeText(
            "Allow this? It will affect your currently focused window."
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        payload["result"]["ok"] = box.exec() == QMessageBox.Yes
        payload["event"].set()

    # ------------------------------------------------------------------
    # Tray callbacks – each runs on its own daemon thread
    # ------------------------------------------------------------------

    def handle_voice_command(self):
        """
        Activated by hotkey or tray 'Talk to Agent'. Runs on a worker thread
        (hotkey/tray), so it must push conversation to the panel via bridge
        signals - never touch Qt widgets directly here.
        """
        if not _processing_lock.acquire(blocking=False):
            notify("Desktop Agent", "Already processing a command, please wait.")
            return
        try:
            # Short-lived STATUS goes through toasts (requirement #5)...
            notify("Desktop Agent", "Listening… speak your command")
            text = self.voice.listen()
            if not text:
                notify("Desktop Agent", "Didn't catch that – try again.")
                return

            # ...CONVERSATION content goes to the floating panel.
            if self.bridge:
                self.bridge.user_said.emit(text)

            response = self.process_user_input(text)

            if self.bridge:
                self.bridge.agent_said.emit(response)
            self.voice.speak(response)
        finally:
            _processing_lock.release()

    def handle_type_command(self):
        """
        Activated by tray 'Type a Command'. Runs on a tray worker thread, so it
        cannot show a Qt dialog itself - it requests one on the GUI thread via
        the bridge. _show_type_dialog() (GUI thread) does the actual input.
        """
        if self.bridge:
            self.bridge.type_requested.emit()

    def _show_type_dialog(self):
        """GUI-thread slot: show the Qt input dialog, then process off-thread."""
        from PySide6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(
            self.panel, "Desktop Agent", "Enter your command:"
        )
        if ok and text.strip():
            threading.Thread(
                target=self._process_command,
                args=(text.strip(),),
                daemon=True,
                name="type-proc",
            ).start()

    def _process_command(self, text: str):
        """Shared worker-thread processing for a typed command."""
        if not _processing_lock.acquire(blocking=False):
            notify("Desktop Agent", "Already processing a command, please wait.")
            return
        try:
            if self.bridge:
                self.bridge.user_said.emit(text)
            response = self.process_user_input(text)
            if self.bridge:
                self.bridge.agent_said.emit(response)
            self.voice.speak(response)
        finally:
            _processing_lock.release()

    def handle_quit(self):
        """Runs on the tray thread - request quit on the GUI thread via bridge."""
        logger.info("Agent shutting down")
        notify("Desktop Agent", "Shutting down…", duration=2)
        if self.bridge:
            self.bridge.quit_requested.emit()

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def run_tray(self):
        """
        Persistent mode: Qt floating panel (main thread) + system tray and
        global hotkey (background threads).

        Thread ownership is INVERTED from the old design: Qt now owns the main
        thread (QApplication.exec), and pystray runs on a daemon thread. This
        is required because QApplication and all widgets must live on one
        thread; per-thread Win32 message loops let pystray coexist safely.
        """
        from PySide6.QtWidgets import QApplication

        from agent.chat_panel import ChatBridge, ChatPanel
        from agent.hotkey import HotkeyListener
        from agent.tray import TrayIcon

        # --- Qt on the MAIN thread ---
        app = QApplication(sys.argv)
        # Closing/hiding the panel must NOT quit the app; only tray "Quit" does.
        app.setQuitOnLastWindowClosed(False)

        self.bridge = ChatBridge()
        self.panel = ChatPanel(self.bridge)
        # These signals must be handled ON the GUI thread:
        self.bridge.quit_requested.connect(app.quit)
        self.bridge.type_requested.connect(self._show_type_dialog)
        self.bridge.confirm_requested.connect(self._on_confirm_requested)
        self.panel.show()

        # --- Hotkey listener on its own daemon thread (unchanged) ---
        hotkey = HotkeyListener(on_activate=self.handle_voice_command)
        hotkey.start()

        # --- Tray on a NEW daemon thread (was the main thread before) ---
        tray = TrayIcon(
            on_voice=self.handle_voice_command,
            on_type=self.handle_type_command,
            on_quit=self.handle_quit,
        )
        tray_thread = threading.Thread(target=tray.run, daemon=True, name="tray")
        tray_thread.start()

        notify(
            "Desktop Agent",
            "Agent is running! Press Ctrl+Shift+A to speak a command.",
        )

        try:
            app.exec()  # blocks the main thread until app.quit()
        finally:
            hotkey.stop()
            tray.stop()

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
