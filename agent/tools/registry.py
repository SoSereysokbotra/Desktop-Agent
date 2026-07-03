"""
Tool Registry - Central repository for all available tools

The registry is a singleton that:
- Stores all registered tools
- Provides lookup by name
- Generates JSON schemas for LLM tool calling
"""

import logging
from typing import Dict, List, Optional

from .base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Singleton registry for all available tools.
    Tools self-register when their modules are imported.
    """

    _instance = None
    _tools: Dict[str, BaseTool] = {}
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """
        Register a tool instance.

        Args:
            tool: Instance of a BaseTool subclass

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in cls._tools:
            logger.warning(f"Tool '{tool.name}' is already registered, overwriting")

        cls._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.category})")

    @classmethod
    def get_tool(cls, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name (case-sensitive)

        Returns:
            Tool instance or None if not found
        """
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[BaseTool]:
        """
        Get all registered tools.

        Returns:
            List of all tool instances
        """
        return list(cls._tools.values())

    @classmethod
    def list_by_category(cls, category: str) -> List[BaseTool]:
        """
        Get all tools in a specific category.

        Args:
            category: Category name (e.g., 'app_control', 'input')

        Returns:
            List of tools in that category
        """
        return [tool for tool in cls._tools.values() if tool.category == category]

    @classmethod
    def get_json_schemas(cls) -> List[Dict]:
        """
        Get JSON schemas for all registered tools.
        Used to provide tool definitions to the LLM.

        Returns:
            List of tool schemas
        """
        return [tool.to_json_schema() for tool in cls._tools.values()]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools (useful for testing)"""
        cls._tools.clear()
        logger.info("Tool registry cleared")

    @classmethod
    def get_tool_names(cls) -> List[str]:
        """Get list of all registered tool names"""
        return list(cls._tools.keys())

    def __repr__(self) -> str:
        return f"<ToolRegistry: {len(self._tools)} tools registered>"
