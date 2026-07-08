"""T1.2 + T1.3: LLM 抽象层、MockLLM、LLM 适配器 测试"""

import json
from unittest.mock import MagicMock, patch

import pytest
from hatch.core.llm import (
    LLMBackend,
    MockLLM,
    OpenAICompatLLM,
    DeepSeekLLM,
    GLMLLM,
    ClaudeLLM,
)


class TestLLMBackend:
    """LLMBackend 抽象基类"""

    def test_cannot_instantiate_abstract(self) -> None:
        """LLMBackend 是抽象类，不能直接实例化"""
        with pytest.raises(TypeError):
            LLMBackend()  # type: ignore[abstract]

    def test_subclass_must_implement_complete(self) -> None:
        """子类必须实现 complete 方法"""
        with pytest.raises(TypeError):
            class Incomplete(LLMBackend):
                pass
            Incomplete()  # type: ignore[abstract]


class TestMockLLM:
    """MockLLM"""

    def test_is_subclass_of_llm_backend(self) -> None:
        mock = MockLLM(["hello"])
        assert isinstance(mock, LLMBackend)

    def test_returns_responses_in_sequence(self) -> None:
        mock = MockLLM(["first", "second", "third"])
        assert mock.complete([]) == "first"
        assert mock.complete([]) == "second"
        assert mock.complete([]) == "third"

    def test_call_count_increments(self) -> None:
        mock = MockLLM(["a", "b"])
        assert mock.call_count == 0
        mock.complete([])
        assert mock.call_count == 1
        mock.complete([])
        assert mock.call_count == 2
        mock.complete([])
        assert mock.call_count == 3

    def test_wraps_around_when_exhausted(self) -> None:
        mock = MockLLM(["one", "two"])
        assert mock.complete([]) == "one"
        assert mock.complete([]) == "two"
        assert mock.complete([]) == "one"   # wraps
        assert mock.complete([]) == "two"
        assert mock.complete([]) == "one"   # wraps again

    def test_messages_parameter_is_accepted(self) -> None:
        """MockLLM 接受 messages 参数但不依赖其内容"""
        mock = MockLLM(["response"])
        result = mock.complete([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a function."},
        ])
        assert result == "response"

    def test_state_independent_per_instance(self) -> None:
        """每个 MockLLM 实例独立维护状态"""
        mock1 = MockLLM(["a"])
        mock2 = MockLLM(["b"])
        assert mock1.complete([]) == "a"
        assert mock2.complete([]) == "b"


class TestOpenAICompatLLM:
    """OpenAICompatLLM 基类"""

    def test_is_subclass_of_llm_backend(self) -> None:
        llm = OpenAICompatLLM("sk-test", "https://api.example.com/v1", "test-model")
        assert isinstance(llm, LLMBackend)

    def test_constructs_correct_request(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        llm = OpenAICompatLLM("sk-test", "https://api.example.com/v1", "test-model")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "world"}}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance

            result = llm.complete(messages)

            mock_instance.post.assert_called_once()
            call_args = mock_instance.post.call_args
            assert call_args[0][0] == "https://api.example.com/v1/chat/completions"
            assert call_args[1]["headers"]["Authorization"] == "Bearer sk-test"
            body = json.loads(call_args[1]["content"])
            assert body["model"] == "test-model"
            assert body["messages"] == messages
            assert result == "world"

    def test_uses_custom_model(self) -> None:
        llm = OpenAICompatLLM("sk-test", "https://api.example.com/v1", "custom-model")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "ok"}}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance
            llm.complete([{"role": "user", "content": "hi"}])
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "custom-model"


class TestDeepSeekLLM:
    """DeepSeekLLM"""

    def test_defaults(self) -> None:
        llm = DeepSeekLLM("sk-test")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "ok"}}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance
            llm.complete([{"role": "user", "content": "hi"}])
            call_url = mock_instance.post.call_args[0][0]
            assert call_url == "https://api.deepseek.com/chat/completions"
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "deepseek-v4-pro"

    def test_custom_model(self) -> None:
        llm = DeepSeekLLM("sk-test", model="deepseek-reasoner")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "ok"}}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance
            llm.complete([{"role": "user", "content": "hi"}])
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "deepseek-reasoner"


class TestGLMLLM:
    """GLMLLM"""

    def test_defaults(self) -> None:
        llm = GLMLLM("sk-test")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "ok"}}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance
            llm.complete([{"role": "user", "content": "hi"}])
            call_url = mock_instance.post.call_args[0][0]
            assert call_url == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "glm-5.2"

    def test_custom_model(self) -> None:
        llm = GLMLLM("sk-test", model="glm-4-plus")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "ok"}}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance
            llm.complete([{"role": "user", "content": "hi"}])
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "glm-4-plus"


class TestClaudeLLM:
    """ClaudeLLM"""

    def test_is_subclass_of_llm_backend(self) -> None:
        llm = ClaudeLLM("sk-ant-test")
        assert isinstance(llm, LLMBackend)

    def test_defaults(self) -> None:
        llm = ClaudeLLM("sk-ant-test")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"content": [{"text": "hello from claude"}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance

            result = llm.complete([{"role": "user", "content": "hi"}])

            call_url = mock_instance.post.call_args[0][0]
            assert call_url == "https://api.anthropic.com/v1/messages"
            headers = mock_instance.post.call_args[1]["headers"]
            assert headers["x-api-key"] == "sk-ant-test"
            assert headers["anthropic-version"] == "2023-06-01"
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "claude-sonnet-4-20250514"
            assert body["max_tokens"] == 4096
            assert result == "hello from claude"

    def test_custom_model(self) -> None:
        llm = ClaudeLLM("sk-ant-test", model="claude-opus-4-20250514")
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"content": [{"text": "ok"}]},
            )
            mock_client.return_value.__enter__.return_value = mock_instance
            llm.complete([{"role": "user", "content": "hi"}])
            body = json.loads(mock_instance.post.call_args[1]["content"])
            assert body["model"] == "claude-opus-4-20250514"