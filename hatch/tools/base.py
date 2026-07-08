"""Tool 抽象基类"""

from abc import ABC, abstractmethod

from hatch.core.models import ToolResult


class Tool(ABC):
    name: str
    description: str
    parameters_schema: dict

    @abstractmethod
    def execute(self, params: dict) -> ToolResult:
        ...