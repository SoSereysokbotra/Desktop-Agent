"""
Planner - Agent decision-making logic

Hybrid routing approach:
1. Regex-based keyword router (fast, deterministic) - tries first
2. LLM JSON fallback (flexible) - used when regex doesn't match but tools are needed

The LLM is also used for generating final natural-language responses.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from agent.tool_utils import normalize_tool_args
from agent.tools import ToolRegistry
from models.llm import LLM

logger = logging.getLogger(__name__)


class ToolDecision:
    """Result of tool decision"""

    def __init__(self, needs_tools, tools=None):
        self.needs_tools = needs_tools
        self.tools = tools or []


# ---------------------------------------------------------------------------
# Rule-based keyword router - Phase 1 subset (5 tools)
# Each entry is: (regex_pattern, tool_name, arg_capture_strategy)
# Patterns are matched case-insensitively against the full user input.
#
# NOTE: detect_tools() returns at most ONE match (breaks on first match)
# ---------------------------------------------------------------------------
TOOL_RULES = [
    # Screenshots
    (r"(take\s+a?\s*screenshot|capture\s+screen|screenshot)", "take_screenshot", None),
    # Applications - specific apps map to open_app with hardcoded arg
    (r"\b(open|launch|start)\s+(google\s+)?chrome\b", "open_app", "chrome"),
    (r"\b(open|launch|start)\s+notepad\b", "open_app", "notepad"),
    (
        r"\b(open|launch|start)\s+(vs\s*code|vscode|visual\s+studio\s+code)\b",
        "open_app",
        "code",
    ),
    (r"\b(open|launch|start)\s+(calc(ulator)?)\b", "open_app", "calc"),
    # Generic open_app fallback - captures the app name from user input
    (r"\b(open|launch|start)\s+(.+)", "open_app", 2),
    # Typing (canonical name: type_text, not "type")
    (
        r"\btype\s+[\"']?(.+?)[\"']?\s*(in|into|on)?\s*(notepad|chrome|vscode)?$",
        "type_text",
        1,
    ),
    # Wait
    (r"\bwait\s+(\d+(?:\.\d+)?)\s*(seconds?)?", "wait", 1),
    # Click - patterns for supported formats (order matters: specific first)
    # Coordinates: the connector word is optional and parens are allowed, so
    # "click at 100,200", "click on 50,60", "click 50,60" and "click (50, 60)"
    # all capture x,y. (Previously only "click at X,Y" matched, so "click on
    # 50,60" fell through to the bare pattern and silently dropped the coords.)
    (r"\bclick\s+(?:at\s+|on\s+)?\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", "click", "COORDS"),
    (r"\bclick\s+(center|middle)", "click", 1),  # "click center"
    (r"\bclick\b", "click", None),  # "click" alone
]


def detect_tools(user_input: str) -> List[Tuple[str, Optional[str]]]:
    """
    Deterministically detect which tools are needed using keyword rules.

    Returns at most ONE match (breaks on first match for exclusivity).

    Returns:
        List of (tool_name, string_arg_or_None) tuples.
        Typically length 0 (no match) or 1 (first match).

    Examples:
        detect_tools("open chrome") → [("open_app", "chrome")]
        detect_tools("wait 5 seconds") → [("wait", "5")]
        detect_tools("click at 100,200") → [("click", "100,200")]
        detect_tools("hello") → []
    """
    text = user_input.strip()
    tools_found = []

    for pattern, tool_name, arg_capture in TOOL_RULES:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Handle different arg capture strategies
            if arg_capture == "COORDS":
                # Special case: click with coordinates - combine into "x,y" string
                x, y = match.group(1), match.group(2)
                arg = f"{x},{y}"
            elif arg_capture is None:
                arg = None
            elif isinstance(arg_capture, int):
                # Capture group index
                arg = match.group(arg_capture).strip()
            else:
                # Literal string (e.g. "chrome" for open_chrome pattern)
                arg = arg_capture

            tools_found.append((tool_name, arg))
            # Stop at first match for exclusivity
            break

    return tools_found


def needs_tools(user_input: str) -> bool:
    """
    Return True if the request requires tool execution.

    This is the single source of truth for "does this need tools?"
    Used by both extract_tools() fallback logic and should_use_tools().
    """
    return len(detect_tools(user_input)) > 0


class Planner:
    def __init__(self, llm):
        self.llm = llm

    def should_use_tools(self, user_input: str) -> ToolDecision:
        """
        Pre-check if tools are needed (regex-only, no LLM fallback).

        DEPRECATED: This is no longer used in the main execution path.
        app.py now calls extract_tools() directly, which handles both
        regex AND LLM JSON fallback. This method is kept for potential
        future use as a quick pre-check API.

        This delegates to needs_tools() - does not reimplement the check.
        """
        return ToolDecision(needs_tools=needs_tools(user_input))

    def extract_tools(self, user_input: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Extract tools using hybrid routing: regex first, LLM JSON fallback.

        Flow:
        1. Try regex-based detection (fast, deterministic)
        2. If match found, normalize args and return
        3. If no match but needs_tools(), try LLM JSON fallback
        4. If no match and not needs_tools(), return empty list

        Returns:
            List of (tool_name, dict_args) tuples

        Raises:
            ValueError: If regex captured args that can't be normalized
                       (e.g. "wait abc" where "abc" can't convert to float)

        Note: The for-loop over regex_tools typically runs only once,
              since detect_tools() returns at most one match (single break).
        """
        # Try regex first (fast, deterministic)
        regex_tools = detect_tools(user_input)  # Returns [(tool_name, string_arg), ...]

        if regex_tools:
            # Convert regex results: (tool_name, string) → (tool_name, dict)
            # ValueError propagates to caller if normalization fails
            result = []
            for tool_name, string_arg in regex_tools:
                args_dict = normalize_tool_args(tool_name, string_arg)
                result.append((tool_name, args_dict))
            return result

        # No regex match - try LLM JSON fallback
        # The LLM will decide if tools are needed or return []
        return self.parse_llm_tool_call(user_input)

    def parse_llm_tool_call(self, user_input: str) -> List[Tuple[str, Dict]]:
        """
        Ask LLM to output tool call as JSON when regex doesn't match.

        This is the fallback path for commands that don't match regex patterns
        but clearly need tool execution.

        Returns:
            List of (tool_name, dict_args) tuples
            Empty list if LLM outputs malformed JSON or no tools

        Error handling:
            - Malformed JSON → log error, return []
            - Missing "tool" field → log error, return []
            - Invalid tool name → returns it anyway, executor will catch
            - Invalid args → returns them anyway, executor will catch
        """
        # Get available tools from registry for LLM context
        tool_schemas = ToolRegistry.get_json_schemas()

        prompt = f"""You are a desktop automation assistant. The user said: "{user_input}"

Available tools (JSON schemas):
{json.dumps(tool_schemas, indent=2)}

Output ONLY valid JSON in this exact format (no other text):
{{"tool": "tool_name", "args": {{"key": "value"}}}}

If multiple tools are needed, output a JSON array:
[
  {{"tool": "tool_name1", "args": {{}}}},
  {{"tool": "tool_name2", "args": {{}}}}
]

JSON output:"""

        response = self.llm.generate(prompt, max_tokens=200)

        # Parse JSON with error handling
        try:
            parsed = json.loads(response.strip())

            # Normalize to list format
            if isinstance(parsed, dict):
                return [(parsed["tool"], parsed.get("args", {}))]
            elif isinstance(parsed, list):
                return [(item["tool"], item.get("args", {})) for item in parsed]
            else:
                logger.error(f"LLM returned unexpected JSON structure: {parsed}")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"LLM output is not valid JSON: {response[:200]}")
            return []

        except (KeyError, TypeError) as e:
            logger.error(f"LLM JSON missing required 'tool' field: {e}")
            return []

    def generate_response(self, user_input: str) -> str:
        """Generate a conversational response without tool context"""
        return self.llm.generate_response(user_input)

    def generate_response_with_context(
        self, user_input: str, tool_results: List
    ) -> str:
        """
        Generate a response after tools have been executed.

        Args:
            user_input: Original user request
            tool_results: List of (tool_name, ToolResult) tuples
        """
        return self.llm.generate_response(user_input, tool_results)
