"""LLM 抽象层 + MockLLM + 适配器"""

import json
from abc import ABC, abstractmethod
from collections.abc import Generator

import httpx


class LLMBackend(ABC):
    """LLM 后端抽象基类"""

    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        """发送消息列表，返回 LLM 响应"""
        ...

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """流式响应，逐块 yield 文本"""
        text = self.complete(messages)
        for i in range(0, len(text), 10):
            yield text[i:i+10]


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
    """OpenAI 兼容 API 后端（DeepSeek、GLM 等国产模型通用）"""

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

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", url, headers=headers, content=json.dumps(body)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


class DeepSeekLLM(OpenAICompatLLM):
    """DeepSeek API 后端"""

    def __init__(self, api_key: str, model: str = "deepseek-v4-pro") -> None:
        super().__init__(api_key, "https://api.deepseek.com", model)


class GLMLLM(OpenAICompatLLM):
    """智谱 GLM API 后端"""

    def __init__(self, api_key: str, model: str = "glm-5.2") -> None:
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

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
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
            "stream": True,
        }
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", url, headers=headers, content=json.dumps(body)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            text = data.get("delta", {}).get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
