"""LLM 输出 → Action 列表 解析器"""

import json
import re

from hatch.core.models import Action

# Anthropic 风格 XML 工具调用（部分模型会输出这种格式）：
# <tool_calls><invoke name="shell_executor"><parameter name="command">dir</parameter></invoke></tool_calls>
_XML_INVOKE_RE = re.compile(
    r"<invoke\s+name=[\"']([^\"']+)[\"']>(.*?)</invoke>", re.DOTALL
)
_XML_PARAM_RE = re.compile(
    r"<parameter\s+name=[\"']([^\"']+)[\"']>(.*?)</parameter>", re.DOTALL
)


class ActionParser:

    @staticmethod
    def parse(llm_output: str) -> list[Action]:
        actions, _ = ActionParser.parse_status(llm_output)
        return actions

    @staticmethod
    def _parse_xml_tool_calls(llm_output: str) -> list[Action] | None:
        """解析 XML 工具调用。返回 None 表示没有 XML 结构。"""
        if "<invoke" not in llm_output:
            return None
        invokes = list(_XML_INVOKE_RE.finditer(llm_output))
        if not invokes:
            # 有 invoke 字样但结构不完整 → 格式错误
            return [] if re.search(r"<invoke\b", llm_output) else None
        actions = []
        for m in invokes:
            name = m.group(1)
            body = m.group(2)
            params: dict[str, str] = {}
            for p in _XML_PARAM_RE.finditer(body):
                params[p.group(1)] = p.group(2).strip()
            actions.append(Action(
                tool_name=name,
                parameters=params,
                raw_llm_output=llm_output,
            ))
        return actions

    @staticmethod
    def parse_status(llm_output: str) -> tuple[list[Action], str]:
        """返回 (actions, status)。

        status:
          - "ok":          解析出动作
          - "empty":        显式空数组 []（收尾信号）
          - "invalid_json": 存在 JSON/XML 工具调用结构但解析失败
          - "no_json":      完全没有工具调用结构（纯文本）
        """
        json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)
        if json_match:
            candidate = json_match.group(1)
        else:
            xml_actions = ActionParser._parse_xml_tool_calls(llm_output)
            if xml_actions is not None:
                if not xml_actions:
                    return [], "invalid_json"
                return xml_actions, "ok"
            array_match = re.search(r"\[.*\]", llm_output, re.DOTALL)
            if array_match:
                candidate = array_match.group(0)
            else:
                return [], "no_json"
        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            return [], "invalid_json"
        if not isinstance(raw, list):
            return [], "invalid_json"
        actions = []
        for item in raw:
            if not isinstance(item, dict) or "tool_name" not in item:
                continue
            actions.append(Action(
                tool_name=item["tool_name"],
                parameters=item.get("parameters", {}),
                raw_llm_output=llm_output,
            ))
        if not actions:
            return [], "empty"
        return actions, "ok"

    @staticmethod
    def extract_text(llm_output: str) -> str:
        """提取代码块之外的自然语言文本"""
        cleaned = re.sub(r"```json\s*.*?\s*```", "", llm_output, flags=re.DOTALL)
        cleaned = re.sub(r"```\w*\s*.*?\s*```", "", cleaned, flags=re.DOTALL)
        # XML 工具调用块：不作为自然语言文本
        cleaned = re.sub(r"<tool_calls>.*?</tool_calls>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"<invoke\b.*?</invoke>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"^\s*\[\s*\]\s*$", "", cleaned)
        cleaned = re.sub(r"^\s*\[[\s\S]*\]\s*$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def has_json_block(llm_output: str) -> bool:
        """检查是否包含 ```json 代码块、裸 JSON 数组或 XML 工具调用"""
        return bool(
            re.search(r"```json", llm_output, re.DOTALL) or
            re.search(r"^\s*\[\s*{", llm_output) or
            re.search(r"^\s*\[\s*\]\s*$", llm_output) or
            re.search(r"<invoke\b", llm_output)
        )