"""上下文组装器"""


class ContextBuilder:
    """组装发送给 LLM 的消息上下文"""

    @staticmethod
    def build(
        task: str,
        tools_desc: str,
        feedback: str = "",
        memory: str = "",
    ) -> list[dict]:
        system_prompt = f"""You are a coding agent. You can use the following tools:

{tools_desc}

Output format: respond with a JSON array of actions, each with "tool_name" and "parameters".
Example:
```json
[{{"tool_name": "file_reader", "parameters": {{"path": "app.py"}}}}]
```"""

        if memory:
            system_prompt += f"\n\nProject context:\n{memory}"

        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        if feedback:
            messages.append({"role": "user", "content": f"Previous attempt feedback:\n{feedback}"})

        messages.append({"role": "user", "content": task})

        return messages