"""
Tools Package - Structured Tool System

This package provides a structured tool system with:
- Pydantic-based argument validation
- Typed return values (ToolResult)
- JSON schema generation for LLM tool calling
- Centralized tool registry

Usage:
    from agent.tools import ToolRegistry

    # Get a tool
    tool = ToolRegistry.get_tool("open_app")

    # Execute with validated args
    result = tool.execute(tool.arguments_schema(app_name="notepad"))

    # Check result
    if result.status == "success":
        print(result.result)

Available tool categories:
- app_control: open_app, open_chrome, close_app, etc.
- input: type_text, click, press_key, move_mouse, scroll
- screen: take_screenshot, analyze_screen
- system: wait, list_open_windows, get_screen_size
"""

# Import tool modules to trigger auto-registration
from . import app_tools, input_tools, system_tools
from .base import BaseTool, ToolArguments, ToolResult
from .registry import ToolRegistry

# Note: screen_tools requires vision_analyzer injection, registered separately

__all__ = [
    "BaseTool",
    "ToolArguments",
    "ToolResult",
    "ToolRegistry",
]


def initialize_tools(vision_analyzer=None):
    """
    Initialize all tools that require external dependencies.

    Args:
        vision_analyzer: VisionAnalyzer instance for screen tools
    """
    # Screen tools and grounded tools both need VisionAnalyzer.
    if vision_analyzer:
        from .screen_tools import register_screen_tools

        register_screen_tools(vision_analyzer)

        from .grounded_tools import register_grounded_tools

        register_grounded_tools(vision_analyzer)


def get_tool_summary():
    """Get a summary of all registered tools for debugging"""
    tools = ToolRegistry.list_tools()

    summary = {"total_tools": len(tools), "by_category": {}, "tools": []}

    for tool in tools:
        if tool.category not in summary["by_category"]:
            summary["by_category"][tool.category] = 0
        summary["by_category"][tool.category] += 1

        summary["tools"].append(
            {
                "name": tool.name,
                "category": tool.category,
                "description": tool.description,
            }
        )

    return summary
