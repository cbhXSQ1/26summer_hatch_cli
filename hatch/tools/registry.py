"""工具注册与分发"""

from hatch.core.models import Action, ToolResult
from hatch.tools.base import Tool


class ToolRegistry:
    """工具注册表"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def dispatch(self, action: Action) -> ToolResult:
        if action.tool_name not in self._tools:
            return ToolResult(
                success=False,
                error=f"unknown tool: {action.tool_name}",
            )
        tool = self._tools[action.tool_name]
        try:
            return tool.execute(action.parameters)
        except Exception as e:
            return ToolResult(success=False, error=str(e))