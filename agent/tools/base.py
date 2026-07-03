"""
Base classes for the structured tool system

All tools inherit from BaseTool and use Pydantic models for:
- Type-safe argument validation
- JSON schema generation for LLM tool calling
- Structured result formats
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ToolArguments(BaseModel):
    """
    Base class for tool arguments.
    Each tool defines its own subclass with specific fields.
    """

    class Config:
        # Allow extra fields for forward compatibility
        extra = "forbid"


class ToolResult(BaseModel):
    """
    Standardized tool execution result.

    Fields:
        status: Either "success" or "error"
        result: Human-readable message describing what happened
        data: Optional structured data (e.g., filepath, pid, coordinates)
    """

    status: str = Field(..., pattern="^(success|error)$")
    result: str
    data: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(
        cls, result: str, data: Optional[Dict[str, Any]] = None
    ) -> "ToolResult":
        """Convenience constructor for success results"""
        return cls(status="success", result=result, data=data or {})

    @classmethod
    def error(cls, result: str, data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        """Convenience constructor for error results"""
        return cls(status="error", result=result, data=data or {})


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    Each tool must define:
    - name: Unique identifier
    - description: What the tool does (for LLM and humans)
    - category: Grouping (app_control, input, screen, system)
    - arguments_schema: Pydantic model class for arguments
    - execute(): Implementation that returns ToolResult
    """

    name: str = ""
    description: str = ""
    category: str = ""
    arguments_schema: type[ToolArguments] = ToolArguments

    def __init_subclass__(cls, **kwargs):
        """Validate that subclasses define required attributes"""
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise ValueError(f"{cls.__name__} must define 'name'")
        if not cls.description:
            raise ValueError(f"{cls.__name__} must define 'description'")

    @abstractmethod
    def execute(self, args: ToolArguments) -> ToolResult:
        """
        Execute the tool with validated arguments.

        Args:
            args: Pydantic-validated arguments

        Returns:
            ToolResult with status, result message, and optional data
        """
        pass

    def to_json_schema(self) -> Dict[str, Any]:
        """
        Generate JSON schema for this tool (for LLM tool calling).

        Returns:
            Schema dict with tool name, description, and parameter definitions
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.arguments_schema.model_json_schema(),
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', category='{self.category}')>"
