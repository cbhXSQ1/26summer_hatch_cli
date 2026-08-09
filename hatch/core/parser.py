"""LLM 输出 → Action 列表 解析器"""

import json
import re

from hatch.core.models import Action


class ActionParser:

    @staticmethod
    def parse(llm_output: str) -> list[Action]:
        actions, _ = ActionParser.parse_status(llm_output)
        return actions

    @staticmethod
    def parse_status(llm_output: str) -> tuple[list[Action], str]:
        """返回 (actions, status)。

        status:
          - "ok":          解析出动作
          - "empty":        显式空数组 []（收尾信号）
          - "invalid_json": 存在 JSON 代码块但解析失败
          - "no_json":      完全没有 JSON 动作块（纯文本）
        """
        json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)
        if json_match:
            candidate = json_match.group(1)
        else:
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
        cleaned = re.sub(r"^\s*\[\s*\]\s*$", "", cleaned)
        cleaned = re.sub(r"^\s*\[[\s\S]*\]\s*$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def has_json_block(llm_output: str) -> bool:
        """检查是否包含 ```json 代码块或裸 JSON 数组"""
        return bool(
            re.search(r"```json", llm_output, re.DOTALL) or
            re.search(r"^\s*\[\s*{", llm_output) or
            re.search(r"^\s*\[\s*\]\s*$", llm_output)
        )