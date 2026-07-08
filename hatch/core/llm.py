"""LLM 抽象层 + MockLLM + 适配器"""

import json
from abc import ABC, abstractmethod

import httpx


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


class OpenAICompatLLM(LLMBackend):
    """OpenAI 兼容 API 后端（DeepSeek、GLM 等国产模型通用）

    base_url 为 API 基础地址，不包含 /chat/completions 后缀，
    由实现类内部拼接。
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def complete(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, content=json.dumps(body))
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class DeepSeekLLM(OpenAICompatLLM):
    """DeepSeek API 后端"""

    def __init__(self, api_key: str, model: str = "deepseek-chat") -> None:
        super().__init__(api_key, "https://api.deepseek.com/v1", model)


class GLMLLM(OpenAICompatLLM):
    """智谱 GLM API 后端"""

    def __init__(self, api_key: str, model: str = "glm-4-flash") -> None:
        super().__init__(api_key, "https://open.bigmodel.cn/api/paas/v4", model)


class ClaudeLLM(LLMBackend):
    """Anthropic Claude API 后端"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, messages: list[dict]) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers=headers, content=json.dumps(body))
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]