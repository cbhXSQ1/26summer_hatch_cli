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

    def test_injects_workdir(self) -> None:
        """工作目录必须注入 system prompt — LLM 不应从历史里猜目录。"""
        messages = ContextBuilder.build(
            task="look around",
            tools_desc="echo: test",
            workdir="D:/project/demo",
        )
        assert "D:/project/demo" in messages[0]["content"]

    def test_injects_shell_environment(self) -> None:
        """system prompt 必须声明 Windows cmd 环境 — LLM 不应生成 PowerShell 命令。"""
        messages = ContextBuilder.build(task="list", tools_desc="echo: test")
        system = messages[0]["content"]
        assert "cmd" in system.lower()
        assert "Get-ChildItem" in system or "PowerShell" in system
        assert "dir" in system


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

    def test_workdir_injected_into_system_prompt(self) -> None:
        """真实工作目录必须出现在 system prompt（防历史目录污染）。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        class RecordingLLM(MockLLM):
            def __init__(self, responses, capture):
                super().__init__(responses)
                self.capture = capture
            def complete(self, messages):
                self.capture.append([dict(m) for m in messages])
                return super().complete(messages)

        captured: list[list[dict]] = []
        llm = RecordingLLM(["```json\n[]\n```"], captured)
        state = AgentLoop().run(
            task="hello",
            llm=llm,
            registry=ToolRegistry(),
            config=Config(),
            workdir="C:/work/proj",
        )
        assert state.status == "success"
        assert "C:/work/proj" in captured[0][0]["content"]

    def test_tool_description_includes_parameter_schema(self) -> None:
        """工具描述必须含参数 schema — LLM 不应幻觉出不存在的参数。"""
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
        llm = RecordingLLM(["```json\n[]\n```"], captured)
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        AgentLoop().run(task="hi", llm=llm, registry=registry, config=Config())
        system = captured[0][0]["content"]
        assert '"command"' in system
        assert "parameters" in system

    def test_consecutive_text_intent_warning_escalates(self) -> None:
        """连续多轮纯文本意图 → 提示升级（提醒格式+说明任务未完成）。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
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
            "\u597d\u7684\uff0c\u6211\u5148\u5217\u51fa\u76ee\u5f55\u5185\u5bb9\u3002",
            "\u6211\u6765\u67e5\u770b\u4e00\u4e0b\u6587\u4ef6\u3002",
            "```json\n[]\n```",
        ], captured)
        state = AgentLoop().run(
            task="\u770b\u770b\u76ee\u5f55",
            llm=llm,
            registry=ToolRegistry(),
            config=Config(),
        )
        assert state.status == "success"
        assert state.round == 3
        round3 = " ".join(m["content"] for m in captured[2])
        assert "\u8fde\u7eed" in round3  # "连续"

    def test_each_round_saved_as_conversation_turn(self) -> None:
        """每一轮的助手文本和工具结果都必须进入会话历史。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        llm = MockLLM([
            "\u597d\u7684\uff0c\u6211\u6267\u884c\u4e00\u4e0b\u3002```json\n"
            '[{"tool_name": "shell_executor", "parameters": {"command": "echo hi"}}]\n```',
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="run echo",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        roles = [t["role"] for t in state.conversation_turns]
        assert "assistant" in roles
        assert "user" in roles
        assistant_msgs = [t for t in state.conversation_turns if t["role"] == "assistant"]
        assert any("\u6267\u884c" in t["content"] for t in assistant_msgs)
        tool_msgs = [t for t in state.conversation_turns if t["role"] == "user"]
        assert any("echo hi" in t["content"] for t in tool_msgs)

    def test_xml_tool_calls_executed_in_loop(self) -> None:
        """LLM 输出 <tool_calls> XML 格式 → 循环必须执行工具，而不是警告空转。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        llm = MockLLM([
            "<tool_calls>\n"
            '<invoke name="shell_executor">\n'
            "<parameter name=\"command\">echo hi</parameter>\n"
            "</invoke>\n"
            "</tool_calls>",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="run echo",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        assert state.round == 2
        assert len(state.history) == 1  # 真的执行了一次工具

    def test_warning_round_not_saved_to_history(self) -> None:
        """纯文本承诺轮（无实际产出）不得写入会话历史 — 防灌注+防缓存膨胀。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM([
            "\u597d\u7684\uff0c\u6211\u5148\u5217\u51fa\u76ee\u5f55\u5185\u5bb9\u3002",
            "```json\n[]\n```",
        ])
        state = AgentLoop().run(
            task="\u770b\u76ee\u5f55",
            llm=llm,
            registry=ToolRegistry(),
            config=Config(),
        )
        assert state.status == "success"
        assert all("\u5217\u51fa" not in t["content"] for t in state.conversation_turns)

    def test_truncated_observation_guides_not_to_rerun(self, tmp_path) -> None:
        """截断提示必须引导 LLM 不要重复执行 — 防"截断追逐"死循环。"""
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
        # 输出 300 行（超过 200 行上限 → 触发截断提示；小输出应完整给 LLM）
        big_output = "line\n" * 300
        llm = RecordingLLM([
            f"""```json
[{{"tool_name": "shell_executor", "parameters": {{"command": "type big.txt"}}}}]
```""",
            "```json\n[]\n```",
        ], captured)
        registry = ToolRegistry()
        from hatch.tools.shell_executor import ShellExecutor
        registry.register(ShellExecutor())
        import subprocess
        from unittest.mock import patch
        with patch("hatch.tools.shell_executor.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=big_output, stderr=""
            )
            state = AgentLoop().run(
                task="\u770b\u5927\u6587\u4ef6",
                llm=llm,
                registry=registry,
                config=Config(),
            )
        assert state.status == "success"
        round2 = " ".join(m["content"] for m in captured[1])
        assert "\u622a\u65ad\u662f\u6b63\u5e38\u7b56\u7565" in round2  # 专属引导语
        assert "\u7f29\u5c0f\u8303\u56f4" in round2  # 缩小范围

    def test_variant_command_repeat_detected(self, tmp_path) -> None:
        """微调参数的命令变体也必须触发重复提示（归一化去重）。"""
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
[{"tool_name": "shell_executor", "parameters": {"command": "dir /b /s *.md"}}]
```""",
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "dir /s /b *.md"}}]
```""",
            "```json\n[]\n```",
        ], captured)
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="\u627e md",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        round3 = " ".join(m["content"] for m in captured[2])
        assert "\u8be5\u547d\u4ee4\u4e0a\u4e00\u8f6e\u5df2\u6267\u884c" in round3  # 重复提示专属文案
        # 重复调用不再展示内容（消除"看完整"诱因）
        assert "hello" not in round3
        assert "\u4e0d\u91cd\u590d\u5c55\u793a" in round3

    def test_duplicate_tool_result_not_duplicated_in_history(self) -> None:
        """相同签名的工具结果只写一次历史 — 防重复轮次膨胀。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        llm = MockLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "echo hello"}}]
```""",
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "echo hello"}}]
```""",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="run twice",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        tool_msgs = [t for t in state.conversation_turns if t["role"] == "user"]
        assert len(tool_msgs) == 1  # 重复结果不重复写

    def test_all_repeat_round_writes_nothing_to_history(self) -> None:
        """全重复轮（结果全部过滤）→ assistant 也不写历史 — 防"assistant 无结果"错位。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        llm = MockLLM([
            "\u597d\u7684\uff0c\u6211\u5217\u4e00\u4e0b\u3002```json\n"
            '[{"tool_name": "shell_executor", "parameters": {"command": "dir"}}]\n```',
            "\u6211\u518d\u770b\u770b\u3002```json\n"
            '[{"tool_name": "shell_executor", "parameters": {"command": "dir"}}]\n```',
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="\u770b\u76ee\u5f55",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        # 第一轮：assistant + user 各一条；第二轮（全重复）：都不写
        assistant_msgs = [t for t in state.conversation_turns if t["role"] == "assistant"]
        tool_msgs = [t for t in state.conversation_turns if t["role"] == "user"]
        assert len(assistant_msgs) == 1
        assert len(tool_msgs) == 1

    def test_text_intent_accumulated_escalation(self) -> None:
        """纯文本承诺累计 3 次（即使不连续）也必须升级提示。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
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
            "\u597d\u7684\uff0c\u6211\u5148\u5217\u51fa\u76ee\u5f55\u3002",           # 承诺 1
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "dir"}}]
```""",
            "\u6211\u518d\u770b\u770b\u6587\u4ef6\u3002",                              # 承诺 2
            "\u8fd8\u6709\u5176\u4ed6\u6587\u6863\uff0c\u6211\u518d\u6765\u770b\u770b\u3002",  # 承诺 3（累计 3）
            "```json\n[]\n```",
        ], captured)
        registry = ToolRegistry()
        from hatch.tools.shell_executor import ShellExecutor
        registry.register(ShellExecutor())
        state = AgentLoop().run(
            task="\u770b\u6587\u4ef6",
            llm=llm,
            registry=registry,
            config=Config(),
        )
        assert state.status == "success"
        # 第 4 轮（承诺 3）之后的反馈 → 第 5 轮消息包含累计升级提示
        round5 = " ".join(m["content"] for m in captured[4])
        assert "\u7d2f\u8ba1" in round5 or "\u8fde\u7eed" in round5

    def test_full_observation_goes_to_llm(self, tmp_path) -> None:
        """小输出必须完整回灌给 LLM（不截断）— 防"截断追逐"死循环。"""
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
        # 54 行输出（README 级别）：完整给 LLM，不得截断
        llm = RecordingLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "type readme.md"}}]
```""",
            "```json\n[]\n```",
        ], captured)
        registry = ToolRegistry()
        from hatch.tools.shell_executor import ShellExecutor as SE
        registry.register(SE())
        import subprocess
        from unittest.mock import patch
        with patch("hatch.tools.shell_executor.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="\n".join(f"content line {i}" for i in range(54)),
                stderr="",
            )
            state = AgentLoop().run(
                task="\u770b readme",
                llm=llm,
                registry=registry,
                config=Config(),
            )
        assert state.status == "success"
        round2 = " ".join(m["content"] for m in captured[1])
        assert "content line 0" in round2
        assert "content line 53" in round2          # 最后一行也在（完整）
        assert "\u622a\u65ad" not in round2          # 没有截断提示

    def test_debug_log_writes_messages_and_raw_output(self, tmp_path, monkeypatch) -> None:
        """HATCH_DEBUG 开关：每轮 messages + LLM 原始输出落盘。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        log = tmp_path / "debug.log"
        monkeypatch.setenv("HATCH_DEBUG", str(log))
        llm = MockLLM(["```json\n[]\n```"])
        state = AgentLoop().run(
            task="\u6d4b\u8bd5",
            llm=llm,
            registry=ToolRegistry(),
            config=Config(),
        )
        assert state.status == "success"
        text = log.read_text(encoding="utf-8")
        assert "Round 1" in text
        assert "messages" in text
        assert "LLM \u539f\u59cb\u8f93\u51fa" in text

    def test_consecutive_text_intent_stops_after_3(self) -> None:
        """连续 3 轮纯文本意图 → 直接 failed 停止，不再空转。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM([
            "\u597d\u7684\uff0c\u6211\u5148\u5217\u51fa\u76ee\u5f55\u3002",
            "\u6211\u518d\u770b\u770b\u6587\u4ef6\u3002",
            "\u8fd8\u6709\u5176\u4ed6\u6587\u6863\uff0c\u6211\u518d\u770b\u770b\u3002",
            "\u6211\u7ee7\u7eed\u67e5\u770b\u3002",
        ])
        state = AgentLoop().run(
            task="\u770b\u76ee\u5f55",
            llm=llm,
            registry=ToolRegistry(),
            config=Config(),
        )
        assert state.status == "failed"
        assert state.round == 3  # 第三轮即停，不空转 12 轮

    def test_tool_result_in_history_is_compressed(self, tmp_path) -> None:
        """会话历史里的工具结果只存前 6 行摘要 — 防历史膨胀+缓存前缀漂移。"""
        from hatch.core.llm import MockLLM
        from hatch.core.loop import AgentLoop
        from hatch.tools.registry import ToolRegistry
        from hatch.tools.shell_executor import ShellExecutor
        from hatch.config.loader import Config

        llm = MockLLM([
            """```json
[{"tool_name": "shell_executor", "parameters": {"command": "type big.txt"}}]
```""",
            "```json\n[]\n```",
        ])
        registry = ToolRegistry()
        registry.register(ShellExecutor())
        import subprocess
        from unittest.mock import patch
        with patch("hatch.tools.shell_executor.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="\n".join(f"line {i}" for i in range(30)), stderr=""
            )
            state = AgentLoop().run(
                task="\u770b\u5927\u6587\u4ef6",
                llm=llm,
                registry=registry,
                config=Config(),
            )
        assert state.status == "success"
        tool_msgs = [t for t in state.conversation_turns if t["role"] == "user"]
        assert len(tool_msgs) == 1
        content = tool_msgs[0]["content"]
        assert "line 0" in content
        assert "line 3" in content
        assert "line 10" not in content  # 前几行之外的内容不进入历史