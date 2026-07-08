"""T1.2: LLM 抽象层 + MockLLM 测试"""

import pytest
from hatch.core.llm import LLMBackend, MockLLM


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