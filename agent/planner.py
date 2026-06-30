"""
Planner - Agent decision-making logic

Tool detection is handled by a rule-based keyword router (fast, reliable).
The LLM is only used for generating the final natural-language response.
"""

import re
import logging
from models.llm import LLM

logger = logging.getLogger(__name__)


class ToolDecision:
    """Result of tool decision"""
    def __init__(self, needs_tools, tools=None):
        self.needs_tools = needs_tools
        self.tools = tools or []


# ---------------------------------------------------------------------------
# Rule-based keyword router
# Each entry is: (regex_pattern, tool_name, arg_group_index_or_None)
# Patterns are matched case-insensitively against the full user input.
# ---------------------------------------------------------------------------
TOOL_RULES = [
    # Screenshots / screen analysis
    (r"(take\s+a?\s*screenshot|capture\s+screen|screenshot)", "screenshot", None),
    (r"(what.*(on|do i have).*screen|analyze\s+screen|what.*(open|running))", "analyze_screen", None),

    # Applications – open
    (r"\b(open|launch|start)\s+(google\s+)?chrome\b", "open_chrome", None),
    (r"\b(open|launch|start)\s+notepad\b", "open_notepad", None),
    (r"\b(open|launch|start)\s+(vs\s*code|vscode|visual\s+studio\s+code)\b", "open_vscode", None),
    (r"\b(open|launch|start)\s+(calc(ulator)?)\b", "open_calculator", None),
    # generic open_app fallback – captures the app name
    (r"\b(open|launch|start)\s+(.+)", "open_app", 2),

    # Applications – close
    (r"\bclose\s+all\s+windows\b", "close_app", None),
    (r"\bclose\s+(chrome|browser)\b", "close_app", None),

    # Keyboard / typing
    (r"\btype\s+[\"']?(.+?)[\"']?\s*(in|into|on)?\s*(notepad|chrome|vscode)?$", "type", 1),

    # List windows
    (r"\b(what|list).*(open|running|have open|windows)\b", "list_open_windows", None),
    (r"\blist\s+open\s+windows\b", "list_open_windows", None),

    # Wait
    (r"\bwait\s+(\d+)\s*(seconds?)?\b", "wait", 1),
]


def detect_tools(user_input: str):
    """
    Deterministically detect which tools are needed using keyword rules.
    Returns a list of (tool_name, arg_or_None) tuples.
    """
    text = user_input.strip()
    tools_found = []

    for pattern, tool_name, arg_group in TOOL_RULES:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            arg = match.group(arg_group).strip() if arg_group else None
            tools_found.append((tool_name, arg))
            # Stop at first match for exclusivity (comment out `break` for multi-tool)
            break

    return tools_found


def needs_tools(user_input: str) -> bool:
    """Return True if the request requires tool execution."""
    return len(detect_tools(user_input)) > 0


class Planner:
    def __init__(self, llm):
        self.llm = llm

    def should_use_tools(self, user_input):
        """
        Decide if we need tools using the keyword router (no LLM call).
        """
        return ToolDecision(needs_tools=needs_tools(user_input))

    def extract_tools(self, user_input):
        """
        Extract which tools to use via the keyword router.
        Returns list of (tool_name, args) tuples.
        """
        tools = detect_tools(user_input)
        logger.info(f"Extracted tools: {tools}")
        return tools

    def generate_response(self, user_input):
        """Generate a response without tool context"""
        return self.llm.generate_response(user_input)

    def generate_response_with_context(self, user_input, tool_results):
        """Generate a response after tools have been executed"""
        return self.llm.generate_response(user_input, tool_results)