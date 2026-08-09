"""Async agent runner — runs AgentLoop in executor thread."""

import asyncio
import os
from hatch.core.loop import AgentLoop
from hatch.core.llm import LLMBackend
from hatch.tools.registry import ToolRegistry
from hatch.config.loader import Config
from hatch.memory.session_manager import SessionManager


async def run_agent_async(
    task: str,
    config: Config,
    llm: LLMBackend,
    registry: ToolRegistry,
    session_manager: SessionManager,
    session_id: str,
    event_queue: asyncio.Queue,
) -> None:
    """Run AgentLoop in background executor, pushing events to async queue."""
    # 固定窗口加载最近历史：前缀稳定 → 上下文缓存命中率更高。
    # 窗口过大会让每次请求的前缀都漂移（新轮次不断追加），缓存全部失效。
    turns = session_manager.get_conversation_turns(session_id, limit=10)

    def _on_event(event: dict) -> None:
        try:
            event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    def _run() -> None:
        loop = AgentLoop()
        state = loop.run(
            task=task,
            llm=llm,
            registry=registry,
            config=config,
            on_event=_on_event,
            conversation_history=turns,
            workdir=os.getcwd(),
        )
        session_manager.update_status(session_id, state.round, state.status)
        session_manager.add_conversation_turn(session_id, "user", task)
        for turn in state.conversation_turns:
            session_manager.add_conversation_turn(session_id, turn["role"], turn["content"])
        event_queue.put_nowait({"_done": True, "status": state.status,
                                 "rounds": state.round, "context_text": state.context_text})

    await asyncio.get_event_loop().run_in_executor(None, _run)
