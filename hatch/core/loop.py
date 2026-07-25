"""Agent 主循环"""

from collections.abc import Callable
from hatch.core.models import LoopState, FeedbackSummary
from hatch.core.llm import LLMBackend, MockLLM
from hatch.core.context import ContextBuilder
from hatch.core.parser import ActionParser
from hatch.tools.registry import ToolRegistry
from hatch.guardrails.chain import GuardrailChain
from hatch.guardrails.hitl import HITLHandler
from hatch.feedback.engine import FeedbackEngine
from hatch.memory.session import SessionMemory
from hatch.config.loader import Config


class AgentLoop:
    """Agent 主循环"""

    def run(
        self,
        task: str,
        llm: LLMBackend,
        registry: ToolRegistry,
        config: Config,
        guardrail_chain: GuardrailChain | None = None,
        hitl: HITLHandler | None = None,
        feedback_engine: FeedbackEngine | None = None,
        memory: SessionMemory | None = None,
        on_event: Callable[[dict], None] | None = None,
    ) -> LoopState:
        max_rounds = config.loop.max_rounds
        feedback_engine = feedback_engine or FeedbackEngine()
        memory = memory or SessionMemory()
        guardrail_chain = guardrail_chain or GuardrailChain()
        hitl = hitl or HITLHandler()

        tools_desc = "\n".join(
            f"- {t.name}: {t.description}" for t in registry.list_tools()
        )

        feedback_text = ""
        state = LoopState(max_rounds=max_rounds)

        def emit(event: dict) -> None:
            if on_event:
                on_event(event)

        for round_num in range(1, max_rounds + 1):
            state.round = round_num
            emit({"type": "round_start", "round": round_num, "max_rounds": max_rounds})

            mem_context = memory.get_relevant_context(task)
            messages = ContextBuilder.build(
                task=task,
                tools_desc=tools_desc,
                feedback=feedback_text,
                memory=mem_context,
            )

            emit({"type": "thinking", "msg": "调用 LLM..."})
            llm_output = llm.complete(messages)
            emit({"type": "llm_output", "text": llm_output[:500]})

            actions = ActionParser.parse(llm_output)

            if not actions:
                emit({"type": "warning", "msg": "LLM 未返回有效动作"})
                state.status = "failed"
                emit({"type": "done", "status": "failed", "rounds": round_num})
                return state

            all_ok = True
            for action in actions:
                emit({
                    "type": "tool_call",
                    "name": action.tool_name,
                    "params": action.parameters,
                })

                result = guardrail_chain.check(action)
                if not result.allowed:
                    if result.requires_approval:
                        emit({
                            "type": "guardrail_approve",
                            "tool": action.tool_name,
                            "reason": result.reason,
                        })
                        if not hitl.request_approval(action):
                            emit({"type": "guardrail_denied"})
                            state.status = "stopped"
                            emit({"type": "done", "status": "stopped", "rounds": round_num})
                            return state
                    else:
                        emit({
                            "type": "guardrail_block",
                            "tool": action.tool_name,
                            "reason": result.reason,
                        })
                        state.status = "stopped"
                        emit({"type": "done", "status": "stopped", "rounds": round_num})
                        return state

                tool_result = registry.dispatch(action)
                emit({
                    "type": "tool_result",
                    "name": action.tool_name,
                    "success": tool_result.success,
                    "output": (tool_result.output or "")[:300],
                })

                summary = feedback_engine.process(action, tool_result, round_num)
                state.history.append(summary)

                emit({
                    "type": "feedback",
                    "success": summary.success,
                    "issues": summary.total_issues,
                    "context": summary.context_for_llm,
                })

                if not summary.success:
                    all_ok = False
                    feedback_text = summary.context_for_llm

            emit({"type": "round_end", "round": round_num, "all_ok": all_ok})
            if all_ok:
                state.status = "success"
                emit({"type": "done", "status": "success", "rounds": round_num})
                return state

        state.status = "failed"
        emit({"type": "done", "status": "failed", "rounds": max_rounds})
        return state
