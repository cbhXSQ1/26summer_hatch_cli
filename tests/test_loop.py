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


class TestAgentLoop:
    """AgentLoop 主循环"""

    def test_single_round_success(self, tmp_path) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.file_reader import FileReader
        from hatch.config.loader import Config

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello", encoding="utf-8")
        file_path = str(test_file).replace("\\", "/")

        llm = MockLLM([
            f"""```json
[{{"tool_name": "file_reader", "parameters": {{"path": "{file_path}"}}}}]
```""",
        ])
        registry = ToolRegistry()
        registry.register(FileReader())
        loop = AgentLoop()
        state = loop.run(
            task="read test.txt",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"

    def test_stops_on_max_rounds(self) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config, LoopConfig

        llm = MockLLM(["```json\n[{\"tool_name\": \"file_reader\", \"parameters\": {\"path\": \"x\"}}]\n```"] * 5)
        registry = ToolRegistry()
        from hatch.tools.file_reader import FileReader
        registry.register(FileReader())
        config = Config(loop=LoopConfig(max_rounds=2))
        state = AgentLoop().run(task="read", llm=llm, registry=registry, config=config)
        assert state.status == "failed"
        assert state.round == 2

    def test_guardrail_stops_on_danger(self) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.guardrails.chain import GuardrailChain
        from hatch.guardrails.rules import DangerousCommandRule
        from hatch.config.loader import Config

        llm = MockLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "rm -rf /"}}]
```""",
        ])
        registry = ToolRegistry()
        chain = GuardrailChain()
        chain.add_rule(DangerousCommandRule())
        state = AgentLoop().run(
            task="clean up",
            llm=llm,
            registry=registry,
            guardrail_chain=chain,
            config=Config(),
        )
        assert state.status == "stopped"