"""
Executor - Execute tools using the structured tool registry
rld

Refactored to use the tool registry with Pydantic validation and structured results.
All tool implementations have been moved to agent/tools/*.py modules.
"""

import logging
from typing import Any, Dict, Optional, Union

from agent.tool_utils import normalize_tool_args
from agent.tools import ToolRegistry, ToolResult, initialize_tools

logger = logging.getLogger(__name__)


class Executor:
    """
    Tool executor using the centralized tool registry.

    Handles tool lookup, argument validation, and execution.
    Returns structured ToolResult objects instead of plain strings.
    """

    def __init__(self, vision_analyzer=None):
        """
        Initialize executor with optional vision analyzer dependency.

        Args:
            vision_analyzer: VisionAnalyzer instance for screenshot tools
        """
        self.vision = vision_analyzer

        # Initialize tool registry with dependencies
        initialize_tools(vision_analyzer=vision_analyzer)

        logger.info(
            f"Executor initialized with {len(ToolRegistry.get_tool_names())} tools"
        )

    def execute(
        self, tool_name: str, args: Union[str, Dict[str, Any], None] = None
    ) -> ToolResult:
        """
        Execute a tool by name with given arguments.

        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments (can be string, dict, or None for backward compatibility)

        Returns:
            ToolResult with status, result message, and optional data

        Examples:
            # New dict-based args
            result = execute("open_app", {"app_name": "notepad"})

            # Old string args (converted to dict internally)
            result = execute("open_app", "notepad")

            # No args
            result = execute("take_screenshot", None)
        """
        # Normalize tool name
        tool_name = tool_name.lower().strip()

        # Look up tool in registry
        tool = ToolRegistry.get_tool(tool_name)

        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
            return ToolResult.error(
                result=f"Unknown tool: {tool_name}",
                data={
                    "tool_name": tool_name,
                    "available_tools": ToolRegistry.get_tool_names(),
                },
            )

        # Initialize to None so we can check if conversion succeeded in error handler
        args_dict = None

        try:
            # Convert args to dict format if needed (using shared function)
            args_dict = normalize_tool_args(tool_name, args)

            # Validate arguments using Pydantic
            validated_args = tool.arguments_schema(**args_dict)
            logger.info(f"Executing tool: {tool_name} with args: {args_dict}")

            # Execute the tool
            result = tool.execute(validated_args)

            logger.info(f"Tool {tool_name} completed with status: {result.status}")
            return result

        except Exception as e:
            # Catch validation errors and execution errors
            logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)

            # Build error data - include converted args if available, otherwise raw args
            error_data = {
                "tool_name": tool_name,
                "error": str(e),
                "args": args_dict if args_dict is not None else None,
                "raw_args": args,
            }

            return ToolResult.error(
                result=f"Failed to execute {tool_name}: {str(e)}",
                data=error_data,
            )

    def get_available_tools(self) -> list:
        """
        Get list of all available tool names.

        Returns:
            List of tool name strings
        """
        return ToolRegistry.get_tool_names()

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dict with tool metadata or None if not found
        """
        tool = ToolRegistry.get_tool(tool_name)
        if tool:
            return {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "schema": tool.to_json_schema(),
            }
        return None
