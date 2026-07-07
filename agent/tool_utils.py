"""
Shared utilities for tool argument handling.

This module provides the single source of truth for converting various argument
formats (string, dict, None) into the dict format expected by Pydantic validation.

Used by both executor.py and planner.py to ensure consistent argument handling
across regex-based and LLM-based tool routing.
"""

import logging
from typing import Any, Dict, Union

logger = logging.getLogger(__name__)


def normalize_tool_args(tool_name: str, args: Union[str, Dict, None]) -> Dict[str, Any]:
    """
    Convert arguments to dict format for Pydantic validation.

    This is the ONLY place where string-to-dict conversion logic lives.
    Both regex-based tool detection and direct dict-based calls use this function.

    Args:
        tool_name: Name of the tool
        args: Arguments in any format:
            - Dict: passed through unchanged
            - String: converted based on tool-specific parsing rules
            - None: converted to empty dict

    Returns:
        Dict of arguments suitable for Pydantic validation

    Raises:
        ValueError: If string args can't be converted to expected types
                   (e.g. "abc" to float for wait, "100,abc" to int,int for click)

    Examples:
        normalize_tool_args("open_app", "notepad") → {"app_name": "notepad"}
        normalize_tool_args("wait", "5") → {"seconds": 5.0}
        normalize_tool_args("click", "100,200") → {"x": 100, "y": 200}
        normalize_tool_args("click", "center") → {"position": "center"}
        normalize_tool_args("click", None) → {}
    """
    # Already a dict - pass through
    if isinstance(args, dict):
        return args

    # None - empty dict (use tool defaults)
    if args is None:
        return {}

    # String args - convert based on tool name
    if isinstance(args, str):
        args = args.strip()

        # Application launching tools
        if tool_name in (
            "open_app",
            "open_chrome",
            "open_notepad",
            "open_vscode",
            "open_calculator",
        ):
            return {"app_name": args} if args else {}

        # Keyboard input tools
        elif tool_name in ("type_text", "type"):
            return {"text": args} if args else {}

        # Wait/sleep tool
        elif tool_name == "wait":
            # Raises ValueError if args is not a valid float
            return {"seconds": float(args)} if args else {}

        # Click tool - three formats supported
        elif tool_name == "click":
            if not args:
                return {}  # Click at current position
            elif args.lower() == "center":
                return {"position": "center"}
            elif "," in args:
                # Parse "x,y" format - raises ValueError if not valid ints
                x, y = map(int, args.split(","))
                return {"x": x, "y": y}
            else:
                return {}  # Unrecognized click arg, use current position

        # Grounded text-click tool - the captured span is the search query
        elif tool_name == "click_text":
            return {"query": args} if args else {}

        # Screenshot tool
        elif tool_name in ("take_screenshot", "screenshot"):
            return {"filepath": args} if args else {}

        # Unknown tool - return empty dict
        # Pydantic will give clear error about missing required fields
        else:
            logger.warning(
                f"Unknown tool for arg conversion: {tool_name}, returning empty args"
            )
            return {}

    # Unknown type - return empty dict
    logger.warning(f"Unexpected args type for {tool_name}: {type(args)}")
    return {}
