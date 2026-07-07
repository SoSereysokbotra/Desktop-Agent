"""
Grounded Tools - Vision-grounded desktop actions.

Tools here combine OCR (VisionAnalyzer) with a physical action. They need the
VisionAnalyzer injected, so - like screen_tools - they are registered via
initialize_tools(), NOT auto-registered on import.

click_text: find visible on-screen text via OCR and click its center. The
coordinate mapping (OCR-pixel -> click-coord) was empirically verified 1:1 at
125% display scaling in Phase 3; click_text relies on that verified path.
"""

import logging

import pyautogui
from pydantic import Field

from .base import BaseTool, ToolArguments, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Tool: click_text
# ============================================================================


class ClickTextArgs(ToolArguments):
    """Arguments for clicking on-screen text located via OCR."""

    query: str = Field(
        ..., description="Visible on-screen text to find and click (e.g. 'Save')"
    )
    min_conf: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Minimum OCR confidence (0-100) for a token to be considered",
    )


class ClickText(BaseTool):
    """Find visible text on screen via OCR and click it."""

    name = "click_text"
    description = "Find visible text on the screen via OCR and click it by name"
    category = "input"
    arguments_schema = ClickTextArgs

    def __init__(self, vision_analyzer=None):
        """
        Args:
            vision_analyzer: VisionAnalyzer instance providing find_text().
        """
        self.vision = vision_analyzer

    def execute(self, args: ClickTextArgs) -> ToolResult:
        """
        Screenshot -> find_text(query) -> click the matched center.

        Never clicks blindly: if the text is not found, returns a clean error
        and does NOT move or click the mouse.

        Returns:
            ToolResult. On success, data includes the matched text, score, and
            the click coordinates.
        """
        if not self.vision:
            return ToolResult.error(
                "Vision module not available",
                data={"error": "VisionAnalyzer not initialized"},
            )

        query = (args.query or "").strip()
        if not query:
            return ToolResult.error(
                "No text query provided to click_text",
                data={"error": "empty_query"},
            )

        try:
            # find_text() screenshots the live screen internally (image=None).
            match = self.vision.find_text(query, min_conf=args.min_conf)
        except Exception as e:
            logger.error(f"click_text OCR lookup failed: {e}", exc_info=True)
            return ToolResult.error(
                result=f"OCR lookup failed for '{query}': {str(e)}",
                data={"error": str(e), "query": query},
            )

        # NOT found -> clean error, no click, no guessed fallback location.
        if not match:
            logger.info(f"click_text: text not found on screen: {query!r}")
            return ToolResult.error(
                result=f"Could not find text: '{query}' on screen",
                data={"query": query, "found": False},
            )

        cx, cy = match["cx"], match["cy"]
        try:
            pyautogui.click(cx, cy)
        except Exception as e:
            logger.error(f"click_text click failed: {e}", exc_info=True)
            return ToolResult.error(
                result=(
                    f"Found '{match['text']}' at ({cx},{cy}) but the click "
                    f"failed: {str(e)}"
                ),
                data={
                    "error": str(e),
                    "query": query,
                    "matched_text": match["text"],
                    "x": cx,
                    "y": cy,
                },
            )

        logger.info(
            f"click_text: clicked {match['text']!r} at ({cx},{cy}) "
            f"for query {query!r} (score={match['score']})"
        )
        return ToolResult.success(
            result=f"Clicked '{match['text']}' at ({cx}, {cy})",
            data={
                "query": query,
                "matched_text": match["text"],
                "score": match["score"],
                "x": cx,
                "y": cy,
            },
        )


# ============================================================================
# Registration (requires VisionAnalyzer injection - not auto-registered)
# ============================================================================


def register_grounded_tools(vision_analyzer=None):
    """
    Register vision-grounded tools.

    Args:
        vision_analyzer: VisionAnalyzer instance to inject into the tools.
    """
    ToolRegistry.register(ClickText(vision_analyzer))
    logger.debug("Registered grounded tools")
