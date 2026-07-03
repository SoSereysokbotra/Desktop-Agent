"""
Screen Tools - Screenshot and Vision Analysis

Tools for capturing and analyzing screen content.
"""

import logging
from typing import Optional

from pydantic import Field

from .base import BaseTool, ToolArguments, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Tool: take_screenshot
# ============================================================================


class TakeScreenshotArgs(ToolArguments):
    """Arguments for taking a screenshot"""

    filepath: str = Field(
        default="screenshot.png", description="Path where screenshot should be saved"
    )


class TakeScreenshot(BaseTool):
    """Take a screenshot of the current screen"""

    name = "take_screenshot"
    description = "Capture a screenshot and save it to a file"
    category = "screen"
    arguments_schema = TakeScreenshotArgs

    def __init__(self, vision_analyzer=None):
        """
        Initialize with optional VisionAnalyzer dependency.

        Args:
            vision_analyzer: VisionAnalyzer instance for screenshot capture
        """
        self.vision = vision_analyzer

    def execute(self, args: TakeScreenshotArgs) -> ToolResult:
        """
        Take a screenshot and save to file.

        Returns:
            ToolResult with success/error and filepath in data
        """
        if not self.vision:
            return ToolResult.error(
                "Vision module not available",
                data={"error": "VisionAnalyzer not initialized"},
            )

        try:
            filepath = args.filepath
            logger.info(f"Taking screenshot: {filepath}")

            saved_path = self.vision.save_screenshot(filepath)

            # Check if save_screenshot returned None (failure)
            if saved_path is None:
                return ToolResult.error(
                    result="Screenshot failed - could not capture or save image",
                    data={
                        "error": "save_screenshot returned None",
                        "filepath": args.filepath,
                    },
                )

            return ToolResult.success(
                result=f"Screenshot saved to {saved_path}",
                data={"filepath": saved_path},
            )

        except Exception as e:
            logger.error(f"Screenshot failed: {e}", exc_info=True)
            return ToolResult.error(
                result=f"Screenshot failed: {str(e)}",
                data={"error": str(e), "filepath": args.filepath},
            )


# ============================================================================
# Auto-register tools
# ============================================================================


def register_screen_tools(vision_analyzer=None):
    """
    Register all screen tools.

    Args:
        vision_analyzer: VisionAnalyzer instance to inject into tools
    """
    ToolRegistry.register(TakeScreenshot(vision_analyzer))
    logger.debug("Registered screen tools")
