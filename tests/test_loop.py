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
            "```json\n[]\n```",  # 收尾：无更多动作
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
        assert state.round == 2

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

    def test_loop_with_hitl_approval(self) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.guardrails.chain import GuardrailChain
        from hatch.guardrails.rules import ApprovalCommandRule
        from hatch.guardrails.hitl import HITLHandler
        from hatch.config.loader import Config

        llm = MockLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "git push --force"}}]
```""",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        chain = GuardrailChain()
        chain.add_rule(ApprovalCommandRule())
        hitl = HITLHandler(input_func=lambda _: "y")
        state = AgentLoop().run(
            task="push changes",
            llm=llm,
            registry=registry,
            guardrail_chain=chain,
            hitl=hitl,
            config=Config(),
        )
        assert state.status != "stopped"

    def test_loop_with_hitl_denial(self) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.guardrails.chain import GuardrailChain
        from hatch.guardrails.rules import ApprovalCommandRule
        from hatch.guardrails.hitl import HITLHandler
        from hatch.config.loader import Config

        llm = MockLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "git push --force"}}]
```""",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        chain = GuardrailChain()
        chain.add_rule(ApprovalCommandRule())
        hitl = HITLHandler(input_func=lambda _: "n")
        state = AgentLoop().run(
            task="push changes",
            llm=llm,
            registry=registry,
            guardrail_chain=chain,
            hitl=hitl,
            config=Config(),
        )
        assert state.status == "stopped"

    def test_loop_with_memory_context(self, tmp_path) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.file_reader import FileReader
        from hatch.memory.session import SessionMemory
        from hatch.config.loader import Config

        test_file = tmp_path / "data.txt"
        test_file.write_text("hello", encoding="utf-8")
        file_path = str(test_file).replace("\\", "/")

        llm = MockLLM([
            f"""```json
[{{"tool_name": "file_reader", "parameters": {{"path": "{file_path}"}}}}]
```""",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(FileReader())
        memory = SessionMemory()
        memory.set("framework", "pytest")
        memory.set("language", "python")
        state = AgentLoop().run(
            task="read data.txt",
            llm=llm,
            registry=registry,
            memory=memory,
            config=Config(),
        )
        assert state.status == "success"

    def test_loop_empty_actions(self) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM(["invalid response with no json"])
        registry = ToolRegistry()
        state = AgentLoop().run(
            task="do something",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"  # 纯文本收尾算成功
        assert "invalid" in state.context_text

    def test_text_with_action_intent_not_complete(self) -> None:
        """文本表达动作意图（"我先列目录"）但未调用工具 → 不算完成，提醒重试。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        # 第一轮：纯文本计划；第二轮：真正调用工具；第三轮：收尾
        llm = MockLLM([
            "好的，我先列出目录内容，再读取关键文件。",
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "dir"}}]
```""",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        from hatch.tools.shell_executor import ShellExecutor
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="看看目录",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        assert state.round == 3
        # 第二轮确实执行了工具
        assert any(h.round_number == 2 for h in state.history)

    def test_invalid_json_retried_not_success(self) -> None:
        """JSON 解析失败 → 提醒重试，而不是静默成功。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM([
            "```json\n[{\"tool_name\": \"shell_executor\", \"parameters\": {\"command\": \"dir\"}},]\n```",  # 尾逗号
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        from hatch.tools.shell_executor import ShellExecutor
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="list",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        assert state.round == 2
        assert len(state.history) == 0  # 没有执行任何工具

    def test_empty_json_is_explicit_done(self) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM(["```json\n[]\n```"])
        registry = ToolRegistry()
        state = AgentLoop().run(
            task="anything",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        assert state.round == 1

    def test_repeated_action_detected(self, tmp_path) -> None:
        """相同命令重复执行时，观察结果附带去重提示。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        class RecordingLLM(MockLLM):
            def __init__(self, responses, capture):
                super().__init__(responses)
                self.capture = capture
            def complete(self, messages):
                self.capture.append([dict(m) for m in messages])
                return super().complete(messages)

        captured: list[list[dict]] = []
        llm = RecordingLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "echo hello"}}]
```""",
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "echo hello"}}]
```""",
            "```json\n[]\n```",
        ], captured)
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="run twice",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        # 第三轮消息里应包含重复提示
        round3 = " ".join(m["content"] for m in captured[2])
        assert "重复" in round3 or "已执行" in round3

    def test_loop_multiple_actions_single_round(self, tmp_path) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.file_reader import FileReader
        from hatch.config.loader import Config

        file1 = tmp_path / "a.txt"
        file1.write_text("content a", encoding="utf-8")
        file2 = tmp_path / "b.txt"
        file2.write_text("content b", encoding="utf-8")
        p1 = str(file1).replace("\\", "/")
        p2 = str(file2).replace("\\", "/")

        llm = MockLLM([
            f"""```json
[{{"tool_name": "file_reader", "parameters": {{"path": "{p1}"}}}},
 {{"tool_name": "file_reader", "parameters": {{"path": "{p2}"}}}}]
```""",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(FileReader())
        state = AgentLoop().run(
            task="read two files",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        assert len(state.history) == 2

    def test_loop_with_feedback_engine(self, tmp_path) -> None:
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.file_reader import FileReader
        from hatch.config.loader import Config, LoopConfig

        test_file = tmp_path / "target.txt"
        test_file.write_text("hello", encoding="utf-8")
        ok_path = str(test_file).replace("\\", "/")
        bad_path = str(tmp_path / "nonexistent.txt").replace("\\", "/")

        llm = MockLLM([
            f"""```json
[{{"tool_name": "file_reader", "parameters": {{"path": "{bad_path}"}}}}]
```""",
            f"""```json
[{{"tool_name": "file_reader", "parameters": {{"path": "{ok_path}"}}}}]
```""",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(FileReader())
        config = Config(loop=LoopConfig(max_rounds=3))
        state = AgentLoop().run(
            task="read the file",
            llm=llm,
            registry=registry,
            config=config,
        )
        assert state.status == "success"
        assert state.round == 3

    def test_consecutive_calls_across_rounds(self, tmp_path) -> None:
        """多步任务：跨轮连续调用（dir → read），观察结果回灌下一轮。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.file_reader import FileReader
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        target = tmp_path / "app.py"
        target.write_text("print('hi')", encoding="utf-8")
        target_path = str(target).replace("\\", "/")

        class RecordingLLM(MockLLM):
            def __init__(self, responses, capture):
                super().__init__(responses)
                self.capture = capture

            def complete(self, messages):
                self.capture.append([dict(m) for m in messages])
                return super().complete(messages)

        captured: list[list[dict]] = []
        llm = RecordingLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "echo hello"}}]
```""",
            f"""```json
[{{"tool_name": "file_reader", "parameters": {{"path": "{target_path}"}}}}]
```""",
            "```json\n[]\n```",
        ], captured)
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        registry.register(FileReader())
        state = AgentLoop().run(
            task="inspect the project",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        # 三轮：shell → file_reader → 收尾
        assert state.status == "success"
        assert state.round == 3
        assert len(state.history) == 2
        # 第二轮消息必须包含第一轮的工具观察结果
        round2_msgs = " ".join(m["content"] for m in captured[1])
        assert "echo hello" in round2_msgs or "shell_executor" in round2_msgs
        assert "成功" in round2_msgs or "hello" in round2_msgs
        # 第三轮（收尾）消息包含第二轮读取内容
        round3_msgs = " ".join(m["content"] for m in captured[2])
        assert "print('hi')" in round3_msgs