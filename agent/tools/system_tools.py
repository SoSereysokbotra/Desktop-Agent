"""
System Tools - System Information and Utilities

Tools for system operations like waiting, getting system info, etc.
"""

import logging
import time

from pydantic import Field

from .base import BaseTool, ToolArguments, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Tool: wait
# ============================================================================


class WaitArgs(ToolArguments):
    """Arguments for wait/sleep operation"""

    seconds: float = Field(
        ...,
        description="Number of seconds to wait",
        ge=0.0,
        le=60.0,  # Max 60 seconds to prevent indefinite hangs
    )


class Wait(BaseTool):
    """Wait/sleep for a specified duration"""

    name = "wait"
    description = "Pause execution for a specified number of seconds"
    category = "system"
    arguments_schema = WaitArgs

    def execute(self, args: WaitArgs) -> ToolResult:
        """
        Sleep for the specified duration.

        Returns:
            ToolResult with success/error and actual wait time in data
        """
        try:
            duration = args.seconds
            logger.info(f"Waiting for {duration} seconds")

            start_time = time.time()
            time.sleep(duration)
            actual_duration = time.time() - start_time

            return ToolResult.success(
                result=f"Waited {duration} seconds",
                data={
                    "requested_seconds": duration,
                    "actual_seconds": round(actual_duration, 3),
                },
            )

        except Exception as e:
            logger.error(f"Wait failed: {e}", exc_info=True)
            return ToolResult.error(
                result=f"Wait failed: {str(e)}", data={"error": str(e)}
            )


# ============================================================================
# Auto-register tools
# ============================================================================


def register_system_tools():
    """Register all system tools"""
    ToolRegistry.register(Wait())
    logger.debug("Registered system tools")


# Auto-register when module is imported
register_system_tools()
