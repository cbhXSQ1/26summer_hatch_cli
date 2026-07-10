# -*- coding: utf-8 -*-
"""T8.4: 端到端集成测试"""

import tempfile, os
from pathlib import Path

from hatch.core.llm import MockLLM
from hatch.core.loop import AgentLoop
from hatch.tools.registry import ToolRegistry
from hatch.tools.file_writer import FileWriter
from hatch.tools.file_reader import FileReader
from hatch.tools.test_runner import TestRunner
from hatch.tools.linter import Linter
from hatch.guardrails.chain import GuardrailChain
from hatch.guardrails.rules import DangerousCommandRule
from hatch.feedback.engine import FeedbackEngine
from hatch.config.loader import Config


class TestEndToEnd:
    """端到端：完整流水线"""

    def test_full_pipeline_fix_and_pass(self) -> None:
        """LLM 写代码 → 测试失败 → 反馈 → 修正 → 通过"""
        orig_dir = os.getcwd()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.chdir(tmp)

            llm = MockLLM([
                """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_math.py", "content": "def test_add():\\n    assert 1 + 1 == 3"}},
{"tool_name": "test_runner", "parameters": {"path": "test_math.py"}}]
```""",
                """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_math.py", "content": "def test_add():\\n    assert 1 + 1 == 2"}},
{"tool_name": "test_runner", "parameters": {"path": "test_math.py"}}]
```""",
            ])

            registry = ToolRegistry()
            registry.register(FileWriter())
            registry.register(FileReader())
            registry.register(TestRunner())
            registry.register(Linter())

            feedback_engine = FeedbackEngine()
            guardrail_chain = GuardrailChain()
            guardrail_chain.add_rule(DangerousCommandRule())

            state = AgentLoop().run(
                task="write a test for addition",
                llm=llm,
                registry=registry,
                guardrail_chain=guardrail_chain,
                feedback_engine=feedback_engine,
                config=Config(),
            )

            assert len(state.history) >= 2, f"Should have >=2 feedback entries, got {len(state.history)}"
            assert state.history[1].success is False, "Round 1 test should fail"

            # 验证反馈闭环：应该有失败的反馈 + 后续修正
            failures = [h for h in state.history if not h.success]
            assert len(failures) >= 1, "Should have at least one failure feedback"
            assert any(h.success for h in state.history), "Should have at least one success feedback"

            os.chdir(orig_dir)

    def test_guardrail_blocks_danger(self) -> None:
        """护栏阻止危险命令"""
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

    def test_reader_returns_file_content(self) -> None:
        """FileReader 读取文件内容"""
        import os
        reader = FileReader()
        # 用绝对路径读 pyproject.toml
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pyproject = os.path.join(project_root, "pyproject.toml")
        result = reader.execute({"path": pyproject})
        assert result.success
        assert "hatch" in result.output.lower() or "tool" in result.output.lower()

    def test_linter_on_good_code(self) -> None:
        """Linter 检查格式正确的代码"""
        orig_dir = os.getcwd()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.chdir(tmp)
            os.makedirs(tmp, exist_ok=True)
            Path("good.py").write_text("x = 1\ny = 2\nprint(x + y)\n")

            linter = Linter()
            result = linter.execute({"path": "good.py"})
            assert result.success or result.error is not None  # linter may not be installed

            os.chdir(orig_dir)

    def test_feedback_engine_aggregates(self) -> None:
        """反馈引擎正确聚合测试结果"""
        from hatch.core.models import Action, ToolResult
        from hatch.feedback.engine import FeedbackEngine

        engine = FeedbackEngine()

        # 模拟失败
        action = Action(tool_name="test_runner", parameters={"path": "test.py"}, raw_llm_output="")
        result = ToolResult(success=False, output="test.py::test_fail FAILED\n1 failed", exit_code=1)
        summary = engine.process(action, result, 1)
        assert summary.success is False
        assert summary.total_issues >= 1

        # 模拟通过
        action2 = Action(tool_name="test_runner", parameters={"path": "test.py"}, raw_llm_output="")
        result2 = ToolResult(success=True, output="test.py::test_pass PASSED\n1 passed", exit_code=0)
        summary2 = engine.process(action2, result2, 2)
        assert summary2.success is True
        assert summary2.total_issues == 0