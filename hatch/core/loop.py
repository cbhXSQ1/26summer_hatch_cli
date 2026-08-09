"""Agent 主循环"""

import json
import os
import re
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

# 观察回灌给 LLM 的行数上限：常规文件（README 54 行、pyproject 70+ 行）
# 应完整给到 LLM，仅对超大输出（如递归目录列表）截断。
# （TUI 显示截断是给人看的，与回灌无关。）
OBS_LINE_LIMIT = 200

# 出现这些词说明 LLM 仍打算采取动作，纯文本回复不应视为完成
ACTION_INTENT_KEYWORDS = [
    "调用", "执行", "读取", "列出", "打开", "创建", "修改", "运行",
    "检查", "查看", "看看", "测试", "修复", "写入", "删除", "移动", "搜索",
    "先", "接下来", "然后", "准备", "尝试", "开始", "我将", "让我",
    "tool", "command", "file", "目录",
]

# 调试开关：HATCH_DEBUG=<文件路径> 时每轮把 messages 与 LLM 原始输出落盘
# （运行时读取 env，便于测试中动态开关）


def _debug_dump(
    tag: str,
    messages: list[dict] | None = None,
    llm_output: str | None = None,
    parse_status: str | None = None,
) -> None:
    debug_path = os.environ.get("HATCH_DEBUG")
    if not debug_path:
        return
    try:
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(f"\n===== {tag} =====\n")
            if messages:
                f.write("--- messages ---\n")
                for m in messages:
                    f.write(f"[{m.get('role')}] {m.get('content', '')[:1500]}\n")
            if llm_output is not None:
                f.write("--- LLM 原始输出 ---\n")
                f.write(llm_output)
                f.write("\n")
            if parse_status is not None:
                f.write(f"--- parse_status: {parse_status} ---\n")
    except OSError:
        pass


def _normalize_cmd(command: str) -> str:
    """命令归一化：小写 + 按空白/管道/分号切 token 后排序，用于变体去重。"""
    tokens = [t for t in re.split(r"[\s|&;]+", command.lower()) if t]
    return " ".join(sorted(tokens))


def _is_conclusion(text: str) -> bool:
    """判断纯文本回复是否像收尾（而非动作计划）。"""
    lower = text.lower()
    return not any(kw in lower for kw in ACTION_INTENT_KEYWORDS)


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
        workdir: str = "",
    ) -> LoopState:
        max_rounds = config.loop.max_rounds
        feedback_engine = feedback_engine or FeedbackEngine()
        memory = memory or SessionMemory()
        guardrail_chain = guardrail_chain or GuardrailChain()
        hitl = hitl or HITLHandler()

        tools_desc = "\n".join(
            f"- {t.name}: {t.description}\n"
            f"  parameters: {json.dumps(t.parameters_schema, ensure_ascii=False)}"
            for t in registry.list_tools()
        )

        feedback_text = ""
        observations_text = ""
        state = LoopState(max_rounds=max_rounds)
        # 已执行过的动作签名（去重检测：相同工具+相同参数视为重复）
        executed_signatures: set[str] = set()
        # 已执行过的 shell 命令归一化主干（微调参数变体也视为重复）
        executed_cmd_cores: set[str] = set()
        # 连续/累计只输出文本（未调用工具）的轮数
        consecutive_text_rounds = 0
        total_text_rounds = 0

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
                workdir=workdir,
            )
            _debug_dump(f"Round {round_num}/{max_rounds} messages", messages=messages)

            emit({"type": "thinking", "msg": "调用 LLM..."})
            llm_output = ""
            for chunk in llm.stream(messages):
                llm_output += chunk
                emit({"type": "stream_chunk", "text": chunk})

            actions, parse_status = ActionParser.parse_status(llm_output)
            _debug_dump(
                f"Round {round_num}/{max_rounds} output",
                llm_output=llm_output,
                parse_status=parse_status,
            )
            assistant_text = ActionParser.extract_text(llm_output).strip()

            if not actions:
                if parse_status in ("ok", "empty"):
                    # 显式空数组 [] = 明确的收尾信号 → 成功
                    if assistant_text:
                        state.context_text = assistant_text
                        state.conversation_turns.append(
                            {"role": "assistant", "content": assistant_text}
                        )
                    state.status = "success"
                    emit({"type": "done", "status": "success", "rounds": round_num})
                    return state

                if parse_status == "invalid_json":
                    # 有 JSON/XML 工具调用结构但解析失败：格式违规，提醒后重试
                    emit({"type": "warning", "msg": "工具调用 JSON 解析失败"})
                    feedback_text = (
                        "你的工具调用 JSON 无法解析。请重新输出，格式必须为：\n"
                        "```json\n"
                        '[{{"tool_name": "...", "parameters": {{...}}}}]\n'
                        "```\n"
                        "如果任务已完成，输出 ```json [] ``` 表示结束。"
                    )
                    emit({"type": "round_end", "round": round_num, "all_ok": False})
                    continue

                # no_json：纯文本回复 —— 只有看起来是收尾才算完成
                if assistant_text and _is_conclusion(assistant_text):
                    state.context_text = assistant_text
                    state.conversation_turns.append(
                        {"role": "assistant", "content": assistant_text}
                    )
                    state.status = "success"
                    emit({"type": "done", "status": "success", "rounds": round_num})
                    return state

                # 文本表达了动作意图（"我先..."、"接下来调用..."）但未实际执行：
                # 不能算完成，提醒格式后重试；连续多轮或累计多次则升级措辞
                consecutive_text_rounds += 1
                total_text_rounds += 1
                emit({"type": "warning", "msg": "LLM 未执行工具调用"})
                if consecutive_text_rounds >= 3:
                    # 连续 3 轮纯文本意图：硬兜底，直接失败停止，不空转
                    state.status = "failed"
                    emit({"type": "round_end", "round": round_num, "all_ok": False})
                    emit({
                        "type": "done",
                        "status": "failed",
                        "rounds": round_num,
                    })
                    return state
                if consecutive_text_rounds >= 2 or total_text_rounds >= 3:
                    feedback_text = (
                        f"你已经累计 {total_text_rounds} 轮（连续 {consecutive_text_rounds} 轮）"
                        "只回复文本，没有执行任何工具调用。\n"
                        "不要再用文字描述打算做什么 —— 直接输出工具调用数组：\n"
                        "```json\n"
                        '[{{"tool_name": "...", "parameters": {{...}}}}]\n'
                        "```\n"
                        "如果任务确实已完成，输出 ```json [] ``` 结束。"
                    )
                else:
                    feedback_text = (
                        "你刚才只回复了文本，没有执行任何工具调用。\n"
                        "如果需要操作文件/命令/测试，必须输出工具调用数组：\n"
                        "```json\n"
                        '[{{"tool_name": "...", "parameters": {{...}}}}]\n'
                        "```\n"
                        "如果任务确实已完成，输出 ```json [] ``` 结束。"
                    )
                emit({"type": "round_end", "round": round_num, "all_ok": False})
                continue

            consecutive_text_rounds = 0
            emit({"type": "llm_output", "text": llm_output[:500]})

            all_ok = True
            round_observations: list[str] = []
            round_repeats: list[bool] = []
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

                # 重复动作检测：相同工具 + 相同参数（完全签名）
                sig = action.tool_name + ":" + json.dumps(
                    action.parameters, sort_keys=True, ensure_ascii=False,
                )
                is_repeat = sig in executed_signatures
                executed_signatures.add(sig)

                # 归一化去重：shell 命令的微调变体（改参数顺序/大小写/空白）
                # 同样视为重复 —— LLM 常靠微调命令绕过完全相同签名检测
                if action.tool_name == "shell_executor":
                    cmd = str(action.parameters.get("command", ""))
                    core = _normalize_cmd(cmd)
                    if core:
                        is_repeat = is_repeat or core in executed_cmd_cores
                        executed_cmd_cores.add(core)

                # 收集观察结果，供下一轮决策使用
                if is_repeat:
                    # 重复调用：不展示内容（结果与上次完全相同），
                    # 消除 LLM"想看到完整输出"而反复重试的诱因
                    params_txt = ", ".join(
                        f"{k}={str(v)[:40]}"
                        for k, v in list(action.parameters.items())[:2]
                    )
                    obs = (
                        f"- 调用 {action.tool_name}({params_txt}) → "
                        "与上一轮相同，结果完全相同，此处不重复展示。\n"
                        "  ⚠ 该命令上一轮已执行，结果如上；"
                        "若结果不满足需求，请说明原因或换一种方式，不要原样重复。"
                    )
                else:
                    obs = self._format_observation(action, tool_result)
                round_observations.append(obs)
                round_repeats.append(is_repeat)

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
            # 历史只写非重复的工具结果（重复轮次无新信息，防历史膨胀）
            fresh_observations = "\n".join(
                obs for obs, rep in zip(round_observations, round_repeats) if not rep
            )
            if fresh_observations:
                # assistant 文本与新鲜结果配对写入：全重复轮既不写
                # assistant 也不写结果，避免历史里出现"说了要做却没结果"的错位
                if assistant_text:
                    state.context_text = assistant_text
                    state.conversation_turns.append(
                        {"role": "assistant", "content": assistant_text}
                    )
                # 历史只存压缩摘要（前 HISTORY_OBS_LINES 行）：
                # 完整观察仅当轮注入，历史膨胀会让上下文缓存前缀漂移
                state.conversation_turns.append({
                    "role": "user",
                    "content": "工具执行结果：\n" + _compress_history_obs(fresh_observations),
                })
            if all_ok:
                # 本轮全部成功：引导 LLM 基于观察结果收尾或继续
                feedback_text = (
                    "上一轮工具调用全部执行成功。\n"
                    "若任务已完成：总结结论并输出 ```json [] ``` 结束。\n"
                    "若还需继续操作：基于上一轮的执行结果调用下一个工具。"
                )

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
                obs += (
                    f"\n    ...(输出共 {len(lines)} 行，已截断显示前 {OBS_LINE_LIMIT} 行。"
                    "截断是正常策略，请基于已有信息继续决策；"
                    "如需更多信息，请用更精确的命令缩小范围，不要重复执行同一命令。)"
                )
        return obs


HISTORY_OBS_LINES = 6


def _compress_history_obs(observations_text: str) -> str:
    """历史里只保留观察结果的前几行摘要（防历史膨胀 + 缓存前缀漂移）。"""
    lines = observations_text.splitlines()
    if len(lines) <= HISTORY_OBS_LINES:
        return observations_text
    head = "\n".join(lines[:HISTORY_OBS_LINES])
    return head + f"\n...(共 {len(lines)} 行，历史仅保留摘要)"
