"""LLM 输出 → Action 列表 解析器"""

import json
import re

from hatch.core.models import Action


class ActionParser:

    @staticmethod
    def parse(llm_output: str) -> list[Action]:
        json_match = re.search(r"```json\s*(.*?)\s*```", llm_output, re.DOTALL)
        if json_match:
            candidate = json_match.group(1)
        else:
            array_match = re.search(r"\[.*\]", llm_output, re.DOTALL)
            if array_match:
                candidate = array_match.group(0)
            else:
                return []
        try:
            raw = json.loads(candidate)
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, list):
            return []
        actions = []
        for item in raw:
            if not isinstance(item, dict) or "tool_name" not in item:
                continue
            actions.append(Action(
                tool_name=item["tool_name"],
                parameters=item.get("parameters", {}),
                raw_llm_output=llm_output,
            ))
        return actions

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