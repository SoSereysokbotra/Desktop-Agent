"""
Input Tools - Keyboard and Mouse Control

Tools for simulating keyboard input and mouse actions.
"""

import logging
from typing import Optional

import pyautogui
from pydantic import Field

from .base import BaseTool, ToolArguments, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Tool: type_text
# ============================================================================


class TypeTextArgs(ToolArguments):
    """Arguments for typing text"""

    text: str = Field(..., description="Text to type via keyboard simulation")
    interval: float = Field(
        default=0.05, description="Delay between keystrokes in seconds", ge=0.0, le=1.0
    )


class TypeText(BaseTool):
    """Type text using keyboard simulation"""

    name = "type_text"
    description = "Type text at the current cursor position"
    category = "input"
    arguments_schema = TypeTextArgs

    def execute(self, args: TypeTextArgs) -> ToolResult:
        """
        Type text character by character.

        Returns:
            ToolResult with success/error and character count in data
        """
        if not args.text:
            return ToolResult.error("No text provided to type")

        try:
            logger.info(
                f"Typing text: '{args.text[:50]}...' (interval={args.interval})"
            )

            # pyautogui.typewrite() only handles ASCII characters
            # It raises an exception for unsupported characters
            pyautogui.typewrite(args.text, interval=args.interval)

            return ToolResult.success(
                result=f"Typed: {args.text}",
                data={
                    "text": args.text,
                    "char_count": len(args.text),
                    "interval": args.interval,
                },
            )

        except Exception as e:
            logger.error(f"Failed to type text: {e}", exc_info=True)
            return ToolResult.error(
                result=f"Could not type text: {str(e)}",
                data={"error": str(e), "text": args.text},
            )


# ============================================================================
# Tool: click
# ============================================================================


class ClickArgs(ToolArguments):
    """Arguments for mouse click"""

    x: Optional[int] = Field(
        default=None,
        description="X coordinate (optional, uses current position if not provided)",
    )
    y: Optional[int] = Field(
        default=None,
        description="Y coordinate (optional, uses current position if not provided)",
    )
    position: Optional[str] = Field(
        default=None,
        description="Named position like 'center' (alternative to x,y coordinates)",
    )


class Click(BaseTool):
    """Click the mouse at a specific position"""

    name = "click"
    description = "Click the mouse at specified coordinates or current position"
    category = "input"
    arguments_schema = ClickArgs

    def execute(self, args: ClickArgs) -> ToolResult:
        """
        Click the mouse.

        Priority: position name > x,y coordinates > current position

        Returns:
            ToolResult with success/error and click coordinates in data
        """
        try:
            # Handle named positions
            if args.position:
                if args.position.lower() == "center":
                    try:
                        screen_width, screen_height = pyautogui.size()
                        x, y = screen_width // 2, screen_height // 2
                        pyautogui.click(x, y)
                        logger.info(f"Clicked at center: ({x}, {y})")

                        return ToolResult.success(
                            result=f"Clicked at center",
                            data={"x": x, "y": y, "position": "center"},
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to get screen size or click: {e}", exc_info=True
                        )
                        return ToolResult.error(
                            result=f"Could not click at center: {str(e)}",
                            data={"error": str(e), "position": "center"},
                        )
                else:
                    return ToolResult.error(
                        result=f"Unknown position: '{args.position}'",
                        data={"error": "invalid_position", "position": args.position},
                    )

            # Handle explicit coordinates
            elif args.x is not None and args.y is not None:
                pyautogui.click(args.x, args.y)
                logger.info(f"Clicked at ({args.x}, {args.y})")

                return ToolResult.success(
                    result=f"Clicked at ({args.x}, {args.y})",
                    data={"x": args.x, "y": args.y},
                )

            # Click at current position
            else:
                try:
                    current_x, current_y = pyautogui.position()
                    pyautogui.click()
                    logger.info(
                        f"Clicked at current position: ({current_x}, {current_y})"
                    )

                    return ToolResult.success(
                        result="Clicked at current position",
                        data={"x": current_x, "y": current_y},
                    )
                except Exception as e:
                    logger.error(f"Failed to get position or click: {e}", exc_info=True)
                    return ToolResult.error(
                        result=f"Could not click at current position: {str(e)}",
                        data={"error": str(e)},
                    )

        except Exception as e:
            logger.error(f"Click failed: {e}", exc_info=True)
            return ToolResult.error(
                result=f"Click failed: {str(e)}", data={"error": str(e)}
            )


# ============================================================================
# Auto-register tools
# ============================================================================


def register_input_tools():
    """Register all input control tools"""
    ToolRegistry.register(TypeText())
    ToolRegistry.register(Click())
    logger.debug("Registered input control tools")


# Auto-register when module is imported
register_input_tools()
