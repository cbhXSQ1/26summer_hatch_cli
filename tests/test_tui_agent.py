# tests/test_tui_agent.py
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from hatch.tui.agent import run_agent_async
from hatch.core.models import LoopState


class TestAgentRunner:
    @pytest.mark.asyncio
    async def test_enqueues_stream_event(self):
        from hatch.core.llm import MockLLM
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM(["hello world"])
        registry = ToolRegistry()
        config = Config()
        config.loop.max_rounds = 1

        state = LoopState()
        state.status = "success"
        state.round = 1
        state.max_rounds = 1

        with patch("hatch.tui.agent.AgentLoop") as mock_loop_class:
            mock_loop = mock_loop_class.return_value
            mock_loop.run.return_value = state

            queue = asyncio.Queue(maxsize=128)
            sm = MagicMock()
            sm.get_conversation_turns.return_value = []

            await run_agent_async(
                task="hello", config=config, llm=llm,
                registry=registry, session_manager=sm,
                session_id="abc", event_queue=queue,
            )

            events = []
            while not queue.empty():
                events.append(queue.get_nowait())

            assert len(events) > 0
            assert events[-1].get("_done") is True
            # 历史窗口固定：只加载最近 N 轮（前缀稳定 → 缓存友好）
            assert sm.get_conversation_turns.call_args.args[0] == "abc"
            assert sm.get_conversation_turns.call_args.kwargs.get("limit", 10) <= 10

    @pytest.mark.asyncio
    async def test_marks_done_on_completion(self):
        from hatch.core.llm import MockLLM
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM(["hello"])
        registry = ToolRegistry()
        config = Config()

        state = LoopState()
        state.status = "success"
        state.round = 1
        state.max_rounds = 1

        with patch("hatch.tui.agent.AgentLoop") as mock_loop_class:
            mock_loop = mock_loop_class.return_value
            mock_loop.run.return_value = state

            queue = asyncio.Queue(maxsize=128)
            sm = MagicMock()
            sm.get_conversation_turns.return_value = []

            await run_agent_async(
                task="hello", config=config, llm=llm,
                registry=registry, session_manager=sm,
                session_id="abc", event_queue=queue,
            )

            found = False
            while not queue.empty():
                e = queue.get_nowait()
                if e.get("_done"):
                    found = True
            assert found

    @pytest.mark.asyncio
    async def test_passes_workdir_and_saves_each_turn(self):
        """run 必须传真实工作目录，并把每轮轮次写进会话历史。"""
        import os
        from hatch.core.llm import MockLLM
        from hatch.tools.registry import ToolRegistry
        from hatch.config.loader import Config

        llm = MockLLM(["hello"])
        registry = ToolRegistry()
        config = Config()

        state = LoopState()
        state.status = "success"
        state.round = 1
        state.max_rounds = 1
        state.conversation_turns = [
            {"role": "assistant", "content": "第一步"},
            {"role": "user", "content": "工具结果：ok"},
        ]

        with patch("hatch.tui.agent.AgentLoop") as mock_loop_class:
            mock_loop = mock_loop_class.return_value
            mock_loop.run.return_value = state

            queue = asyncio.Queue(maxsize=128)
            sm = MagicMock()
            sm.get_conversation_turns.return_value = []

            await run_agent_async(
                task="hello", config=config, llm=llm,
                registry=registry, session_manager=sm,
                session_id="abc", event_queue=queue,
            )

            call_kwargs = mock_loop.run.call_args.kwargs
            assert call_kwargs.get("workdir") == os.getcwd()
            sm.add_conversation_turn.assert_any_call("abc", "assistant", "第一步")
            sm.add_conversation_turn.assert_any_call("abc", "user", "工具结果：ok")
