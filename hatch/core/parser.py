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