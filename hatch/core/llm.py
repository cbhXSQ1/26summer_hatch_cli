"""LLM 抽象层 + MockLLM"""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """LLM 后端抽象基类"""

    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        """发送消息列表，返回 LLM 响应"""
        ...


class MockLLM(LLMBackend):
    """Mock LLM：返回预编程的响应序列，用于确定性测试"""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0

    def complete(self, messages: list[dict]) -> str:
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response