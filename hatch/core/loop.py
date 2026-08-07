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

OBS_LINE_LIMIT = 20


class AgentLoop:
    """Agent 主循环

    语义：LLM 每轮决定要做什么；工具调用成功 ≠ 任务完成。
    只有 LLM 不再产生动作（文本收尾 / 空 JSON）才算完成。
    每轮的工具执行结果（observation）会回灌到下一轮上下文，
    支撑多步连续调用（如 列出目录 → 读取文件 → 得出结论）。
    """

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
        conversation_history: list[dict] | None = None,
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
        observations_text = ""
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
                conversation_history=conversation_history,
                observations=observations_text,
            )

            emit({"type": "thinking", "msg": "调用 LLM..."})
            llm_output = ""
            for chunk in llm.stream(messages):
                llm_output += chunk
                emit({"type": "stream_chunk", "text": chunk})

            actions = ActionParser.parse(llm_output)

            if not actions:
                text_response = ActionParser.extract_text(llm_output)
                has_json = ActionParser.has_json_block(llm_output)

                if text_response.strip():
                    state.context_text = text_response.strip()
                    state.status = "success"
                    emit({"type": "done", "status": "success", "rounds": round_num})
                    return state

                if has_json:
                    state.status = "success"
                    emit({"type": "done", "status": "success", "rounds": round_num})
                    return state

                emit({"type": "warning", "msg": "LLM 未返回有效 JSON 动作"})
                state.status = "failed"
                emit({"type": "done", "status": "failed", "rounds": round_num})
                return state

            emit({"type": "llm_output", "text": llm_output[:500]})

            # 保存 LLM 的自然语言推理作为助手回复
            assistant_text = ActionParser.extract_text(llm_output).strip()
            if assistant_text:
                state.context_text = assistant_text

            all_ok = True
            round_observations: list[str] = []
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

                # 收集观察结果，供下一轮决策使用
                round_observations.append(self._format_observation(
                    action, tool_result,
                ))

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

            observations_text = "\n".join(round_observations)
            if all_ok:
                # 本轮全部成功：清掉旧的失败反馈，让 LLM 基于观察结果继续
                feedback_text = ""

            emit({"type": "round_end", "round": round_num, "all_ok": all_ok})
            # 工具成功不代表任务完成 —— 继续下一轮，
            # 由 LLM 根据观察结果决定继续调用还是文本收尾。

        state.status = "failed"
        emit({"type": "done", "status": "failed", "rounds": max_rounds})
        return state

    @staticmethod
    def _format_observation(action, tool_result: object) -> str:
        """把一次工具调用的结果格式化为可回灌的文本。"""
        from hatch.core.models import ToolResult
        result = tool_result  # type: ToolResult
        detail = result.output or result.error or ""
        status = "成功" if result.success else "失败"
        params = ", ".join(
            f"{k}={str(v)[:60]}" for k, v in list(action.parameters.items())[:3]
        )
        obs = f"- 调用 {action.tool_name}({params}) → {status}"
        if detail:
            lines = detail.splitlines()
            shown = lines[:OBS_LINE_LIMIT]
            obs += "\n  输出:\n" + "\n".join(f"    {l}" for l in shown)
            if len(lines) > OBS_LINE_LIMIT:
                obs += f"\n    ...(共 {len(lines)} 行，截断显示)"
        return obs
