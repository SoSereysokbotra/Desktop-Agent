"""
Application Control Tools

Tools for opening and closing applications on Windows.
"""

import logging
import os
import time

from pydantic import Field

from .base import BaseTool, ToolArguments, ToolResult
from .registry import ToolRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# Tool: open_app
# ============================================================================


class OpenAppArgs(ToolArguments):
    """Arguments for opening an application"""

    app_name: str = Field(
        ...,
        description="Name or path of the application to open (e.g., 'notepad', 'chrome')",
    )


class OpenApp(BaseTool):
    """Open an application by name using Windows startfile"""

    name = "open_app"
    description = "Open an application by name or path"
    category = "app_control"
    arguments_schema = OpenAppArgs

    def execute(self, args: OpenAppArgs) -> ToolResult:
        """
        Open an application using os.startfile.

        Returns:
            ToolResult with success/error and app name in data
        """
        app_name = args.app_name.strip()

        if not app_name:
            return ToolResult.error("No app name provided")

        try:
            logger.info(f"Opening application: {app_name}")

            # os.startfile raises FileNotFoundError for invalid paths
            # It raises OSError for other system-level failures
            os.startfile(app_name)
            time.sleep(2)  # Wait for app to launch

            return ToolResult.success(
                result=f"Opened {app_name}", data={"app_name": app_name}
            )

        except FileNotFoundError:
            logger.error(f"Application not found: {app_name}")
            return ToolResult.error(
                result=f"Application '{app_name}' not found",
                data={"app_name": app_name, "error": "FileNotFoundError"},
            )

        except OSError as e:
            logger.error(f"OS error opening {app_name}: {e}", exc_info=True)
            return ToolResult.error(
                result=f"Could not open {app_name}: {str(e)}",
                data={"app_name": app_name, "error": str(e)},
            )

        except Exception as e:
            logger.error(f"Unexpected error opening {app_name}: {e}", exc_info=True)
            return ToolResult.error(
                result=f"Could not open {app_name}: {str(e)}",
                data={"app_name": app_name, "error": str(e)},
            )


# ============================================================================
# Auto-register tools
# ============================================================================


def register_app_tools():
    """Register all application control tools"""
    ToolRegistry.register(OpenApp())
    logger.debug("Registered app control tools")


# Auto-register when module is imported
register_app_tools()
