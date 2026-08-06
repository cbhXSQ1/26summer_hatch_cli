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
            assert events[0]["type"] == "round_start"

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
