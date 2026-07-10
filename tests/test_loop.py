"""T4.2: ContextBuilder 测试"""

from hatch.core.context import ContextBuilder


class TestContextBuilder:
    """ContextBuilder"""

    def test_builds_messages_with_task(self) -> None:
        tools_desc = "echo: Returns the input"
        messages = ContextBuilder.build(
            task="fix the bug in app.py",
            tools_desc=tools_desc,
        )
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert "echo" in messages[0]["content"]
        assert messages[-1]["role"] == "user"
        assert "fix the bug" in messages[-1]["content"]

    def test_injects_feedback(self) -> None:
        feedback = "Test failed: AssertionError in test_add"
        messages = ContextBuilder.build(
            task="fix the bug",
            tools_desc="echo: test",
            feedback=feedback,
        )
        assert any("Test failed" in m["content"] for m in messages)

    def test_includes_memory(self) -> None:
        memory_context = "User prefers pytest over unittest"
        messages = ContextBuilder.build(
            task="write tests",
            tools_desc="echo: test",
            memory=memory_context,
        )
        assert any("pytest" in m["content"] for m in messages)

    def test_output_format_instruction_present(self) -> None:
        messages = ContextBuilder.build(task="do something", tools_desc="echo: test")
        system = messages[0]["content"]
        assert "json" in system.lower() or "tool_name" in system.lower()