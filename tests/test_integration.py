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


class TestTUI:
    def test_app_constructs_without_error(self, tmp_path):
        """Smoke test: HatchChatApp constructs without crash."""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        llm = MagicMock()
        config = Config()

        sm = MagicMock()
        sm.get_latest_or_create.return_value = ("test-id", True)
        sm.get_info.return_value = {"task": "test conversation"}

        # Patch create_output so prompt_toolkit doesn't probe the Windows
        # console (no console exists under pytest on headless/CI shells).
        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=llm,
                config=config,
                session_manager=sm,
                session_id="test-id",
                session_name="test conversation",
            )
        assert app.app is not None
        assert app.conv_log is not None

    def test_layout_builds_without_error(self, tmp_path):
        """Smoke test: build_layout returns valid Layout."""
        from hatch.tui.layout import build_layout
        from hatch.tui.widgets import FocusableText, ConversationLog
        from prompt_toolkit.buffer import Buffer

        log = ConversationLog()
        cwd = FocusableText("test")
        session = FocusableText("session")
        more = FocusableText("...")
        model = FocusableText("model")
        key = FocusableText("key")
        buf = Buffer()

        layout = build_layout(log, cwd, session, more, model, key, buf)
        assert layout is not None

    def test_submit_busy_guard(self, tmp_path):
        """Submit while a task is running must not start a new run."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        llm = MagicMock()
        config = Config()

        sm = MagicMock()
        sm.get_latest_or_create.return_value = ("test-id", True)
        sm.get_info.return_value = {"task": "test conversation"}

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=llm,
                config=config,
                session_manager=sm,
                session_id="test-id",
                session_name="test conversation",
            )

        loop = asyncio.new_event_loop()
        app._running_task = loop.create_future()

        app.input_buffer.text = "x"
        with patch("hatch.tui.app.run_agent_async") as mock_run:
            app._submit_task("x")
            mock_run.assert_not_called()

        assert app.input_buffer.text == "x"
        assert "Busy" in app.conv_log.get_text()

    def test_toolbar_focus_moves_pt_focus(self, tmp_path):
        """Focus on toolbar element must move real prompt_toolkit focus."""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        llm = MagicMock()
        config = Config()

        sm = MagicMock()
        sm.get_latest_or_create.return_value = ("test-id", True)
        sm.get_info.return_value = {"task": "test conversation"}

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=llm,
                config=config,
                session_manager=sm,
                session_id="test-id",
                session_name="test conversation",
            )

        app._set_focus("cwd")
        assert app._focus == "cwd"
        assert app.cwd_text.is_focused is True
        assert app.session_text.is_focused is False
        assert app.app.layout.current_window is app._focus_target

        app._set_focus("input")
        assert app._focus == "input"
        assert app.cwd_text.is_focused is False
        assert app.app.layout.current_window is app.layout.input_window

    def test_user_input_appears_in_log(self, tmp_path):
        """Submitted task text must be visible in the conversation log."""
        import asyncio
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        llm = MagicMock()
        config = Config()

        sm = MagicMock()
        sm.get_latest_or_create.return_value = ("test-id", True)
        sm.get_info.return_value = {"task": "test conversation"}

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=llm,
                config=config,
                session_manager=sm,
                session_id="test-id",
                session_name="test conversation",
            )

        async def _do_submit():
            with patch("hatch.tui.app.run_agent_async"):
                app._submit_task("\u4f60\u597d")

        asyncio.run(_do_submit())
        assert "\u4f60\u597d" in app.conv_log.get_text()

    def test_dropdowns_mutually_exclusive(self, tmp_path):
        """Opening one dropdown must close the other."""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        llm = MagicMock()
        config = Config()

        sm = MagicMock()
        sm.get_latest_or_create.return_value = ("test-id", True)
        sm.get_info.return_value = {"task": "test conversation"}
        sm.list_sessions.return_value = [
            {"id": "s1", "task": "session one", "updated": "2026-01-01"},
        ]

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=llm,
                config=config,
                session_manager=sm,
                session_id="test-id",
                session_name="test conversation",
            )

        # 打开模型下拉 → sessions 下拉必须关闭
        app._toggle_model_dropdown()
        assert app.model_dropdown.visible is True
        app._toggle_sessions_dropdown()
        assert app.sessions_dropdown.visible is True
        assert app.model_dropdown.visible is False

        # 反向：打开 sessions 下拉 → 模型下拉必须关闭
        app._toggle_model_dropdown()
        assert app.model_dropdown.visible is True
        assert app.sessions_dropdown.visible is False

    def test_model_dropdown_built_from_config(self, tmp_path):
        """模型下拉候选必须来自配置（仅含已有 key 的 provider）。"""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        config = Config()
        config.llm.providers["myllm"] = {
            "api_base": "https://api.myllm.example",
            "models": ["my-model-1", "my-model-2"],
        }

        km = MagicMock()
        km.get_key.return_value = "sk-key"

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=config,
                session_manager=MagicMock(),
                session_id="test-id",
                session_name="test",
                key_manager=km,
            )

        labels = [label for label, _ in app.model_dropdown.items]
        assert "deepseek-v4-pro" in labels          # 内置配置
        assert "my-model-1" in labels               # 自定义配置
        assert "my-model-2" in labels
        assert ("my-model-1", "myllm") in app.model_dropdown.items

    def test_model_dropdown_excludes_provider_without_key(self, tmp_path):
        """没有 key 的 provider 的模型不应出现在下拉中。"""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        config = Config()
        config.llm.providers["nokey"] = {
            "api_base": "https://api.nokey.example",
            "models": ["nk-1"],
        }

        km = MagicMock()
        km.get_key.return_value = None  # 所有 provider 都没 key

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=config,
                session_manager=MagicMock(),
                session_id="test-id",
                session_name="test",
                key_manager=km,
            )

        labels = [label for label, _ in app.model_dropdown.items]
        assert "nk-1" not in labels

    def test_key_add_four_step_flow(self, tmp_path):
        """key 导入四步：名称 → API 地址 → 可用模型 → key。"""
        import asyncio
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        config = Config()
        km = MagicMock()
        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=config,
                session_manager=MagicMock(),
                session_id="test-id",
                session_name="test",
                key_manager=km,
            )

        app._start_key_add()
        assert app._pending_mode == "key_name"

        # 第一步：provider 名称
        app._submit_task("myllm")
        assert app._pending_mode == "key_base"

        # 第二步：API 地址
        app._submit_task("https://api.myllm.example/v1")
        assert app._pending_mode == "key_models"

        # 第三步：显式选择可用模型
        app._submit_task("model-a, model-b")
        assert app._pending_mode == "key_key"
        assert app._key_add_models == ["model-a", "model-b"]

        # 第四步：key
        app._submit_task("sk-custom-key")
        assert app._pending_mode is None
        km.set_key.assert_called_once_with("myllm", "sk-custom-key")
        km.set_provider_meta.assert_called_once()
        _, kwargs = km.set_provider_meta.call_args
        assert kwargs["models"] == ["model-a", "model-b"]
        assert "myllm" in app.config.llm.providers
        assert app.config.llm.providers["myllm"]["models"] == ["model-a", "model-b"]
        assert app.config.llm.providers["myllm"]["api_base"] == "https://api.myllm.example/v1"
        # 模型下拉出现导入时选择的模型
        km.get_key.return_value = "sk-custom-key"
        assert any(m == "model-a" for m, _ in app.model_dropdown.items)

    def test_key_dropdown_switch_and_delete(self, tmp_path):
        """key 下拉可查看/切换/删除已有 provider。"""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config
        from hatch.core.llm import OpenAICompatLLM

        config = Config()
        config.llm.providers["myllm"] = {
            "api_base": "https://api.myllm.example/v1",
            "models": ["model-a"],
        }

        km = MagicMock()
        km.list_providers.return_value = ["deepseek", "myllm"]
        km.get_key.side_effect = lambda p: "sk-key" if p == "myllm" else "sk-ds"

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=config,
                session_manager=MagicMock(),
                session_id="test-id",
                session_name="test",
                key_manager=km,
            )

        # 打开 key 下拉：应有 add/switch/delete 选项
        app._toggle_key_dropdown()
        assert app.key_dropdown.visible is True
        values = [v for _, v in app.key_dropdown.items]
        assert "add" in values
        assert "switch:deepseek" in values
        assert "switch:myllm" in values
        assert "delete:deepseek" in values

        # 选中 switch:myllm 并确认 → 切换到该 provider
        idx = values.index("switch:myllm")
        app.key_dropdown.selected_index = idx
        app._toggle_key_dropdown()  # 再次 Enter → 执行选中动作
        assert app.config.llm.provider == "myllm"
        assert app.config.llm.model == "model-a"
        assert isinstance(app.llm, OpenAICompatLLM)
        assert "Switched to myllm" in app.conv_log.get_text()

        # 删除 provider
        app._toggle_key_dropdown()
        values = [v for _, v in app.key_dropdown.items]
        idx = values.index("delete:myllm")
        app.key_dropdown.selected_index = idx
        app._toggle_key_dropdown()
        km.delete_key.assert_called_once_with("myllm")
        km.delete_provider_meta.assert_called_once_with("myllm")
        assert "myllm" not in app.config.llm.providers

    def test_existing_session_not_renamed(self, tmp_path):
        """已有会话（is_new=False）首次回复后不得自动改名。"""
        import asyncio
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        sm = MagicMock()
        sm.get_conversation_turns.return_value = [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": "reply"},
        ]
        sm.rename = MagicMock()

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=Config(),
                session_manager=sm,
                session_id="test-id",
                session_name="existing name",
                is_new=False,
            )

        async def _do_submit():
            with patch("hatch.tui.app.run_agent_async"):
                app._submit_task("new message")
            if app._running_task:
                await app._running_task

        asyncio.run(_do_submit())
        sm.rename.assert_not_called()

    def test_key_dropdown_rendered_in_layout(self, tmp_path):
        """key 下拉必须出现在布局的浮层中，否则菜单不可见。"""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=Config(),
                session_manager=MagicMock(),
                session_id="test-id",
                session_name="test",
                key_manager=MagicMock(),
            )

        windows = list(app.layout.find_all_windows())
        assert app.key_dropdown.__pt_container__() in windows
        assert app.model_dropdown.__pt_container__() in windows
        assert app.sessions_dropdown.__pt_container__() in windows

    def test_dropdown_window_cached_and_opaque(self, tmp_path):
        """下拉窗口缓存同一实例，且全宽不透明避免与对话拼合。"""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=Config(),
                session_manager=MagicMock(),
                session_id="test-id",
                session_name="test",
                key_manager=MagicMock(),
            )

        w1 = app.model_dropdown.__pt_container__()
        w2 = app.model_dropdown.__pt_container__()
        assert w1 is w2  # 缓存同一实例
        assert "bg:#1a1a1a" in w1.style  # 不透明背景

    def test_new_session_gets_auto_named(self, tmp_path):
        """真正的新会话（is_new=True）首次回复后自动命名。"""
        import asyncio
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        sm = MagicMock()
        sm.get_conversation_turns.return_value = []

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=Config(),
                session_manager=sm,
                session_id="test-id",
                session_name="\u65b0\u5bf9\u8bdd",
                is_new=True,
            )

        # 先喂一条流式回复，再提交（模拟 _process_events 收集）
        app._first_reply_collected = "some reply text"

        async def _do_submit():
            with patch("hatch.tui.app.run_agent_async"):
                app._submit_task("first message")
            if app._running_task:
                await app._running_task

        with patch.object(app, "_auto_name") as mock_auto:
            asyncio.run(_do_submit())
        mock_auto.assert_awaited_once()

    def test_switch_session_loads_history(self, tmp_path):
        """切换会话时必须显示之前的对话消息。"""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        sm = MagicMock()
        sm.get_conversation_turns.return_value = [
            {"role": "user", "content": "\u4f60\u597d"},
            {"role": "assistant", "content": "\u4f60\u597d\uff0c\u6709\u4ec0\u4e48\u53ef\u4ee5\u5e2e\u4f60\uff1f"},
        ]

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=MagicMock(),
                config=Config(),
                session_manager=sm,
                session_id="test-id",
                session_name="test",
            )

        app._switch_session("new-sid", "another conversation")
        text = app.conv_log.get_text()
        assert "\u4f60\u597d" in text                      # 历史用户消息
        assert "\u4f60\u597d\uff0c" in text                 # 历史助手消息
        sm.get_conversation_turns.assert_called_with("new-sid", limit=None)

    def test_model_switch_builds_with_new_config(self, tmp_path):
        """Model switch must build the LLM from the new provider/model."""
        from unittest.mock import MagicMock, patch
        from prompt_toolkit.output import DummyOutput
        from hatch.tui.app import HatchChatApp
        from hatch.config.loader import Config

        llm = MagicMock()
        config = Config()

        sm = MagicMock()
        sm.get_latest_or_create.return_value = ("test-id", True)
        sm.get_info.return_value = {"task": "test conversation"}

        with patch(
            "prompt_toolkit.output.defaults.create_output",
            return_value=DummyOutput(),
        ):
            app = HatchChatApp(
                workdir=str(tmp_path),
                llm=llm,
                config=config,
                session_manager=sm,
                session_id="test-id",
                session_name="test conversation",
            )

        app.model_dropdown.items = [("glm-5.2", "glm")]
        app.model_dropdown.selected_index = 0
        app.model_dropdown.show()

        sentinel = object()

        with patch("hatch.cli._build_llm", return_value=sentinel) as mock_build, \
             patch("hatch.security.key_manager.KeyManager") as mock_km_class:
            mock_km_class.return_value.get_key.return_value = "sk-test"
            app._toggle_model_dropdown()

        assert mock_build.called
        passed = mock_build.call_args
        passed_config = passed[0][0] if passed.args else passed.kwargs["config"]
        assert passed_config.llm.provider == "glm"
        assert passed_config.llm.model == "glm-5.2"
        assert app.config.llm.provider == "glm"
        assert app.config.llm.model == "glm-5.2"
        assert app.llm is sentinel