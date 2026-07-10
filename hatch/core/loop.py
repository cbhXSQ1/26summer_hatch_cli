"""Agent 主循环"""

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

        for round_num in range(1, max_rounds + 1):
            state.round = round_num

            mem_context = memory.get_relevant_context(task)
            messages = ContextBuilder.build(
                task=task,
                tools_desc=tools_desc,
                feedback=feedback_text,
                memory=mem_context,
            )

            llm_output = llm.complete(messages)
            actions = ActionParser.parse(llm_output)

            if not actions:
                state.status = "failed"
                return state

            all_ok = True
            for action in actions:
                result = guardrail_chain.check(action)
                if not result.allowed:
                    if result.requires_approval:
                        if not hitl.request_approval(action):
                            state.status = "stopped"
                            return state
                    else:
                        state.status = "stopped"
                        return state

                tool_result = registry.dispatch(action)
                summary = feedback_engine.process(action, tool_result, round_num)
                state.history.append(summary)
                if not summary.success:
                    all_ok = False
                    feedback_text = summary.context_for_llm

            if all_ok:
                state.status = "success"
                return state

        state.status = "failed"
        return state