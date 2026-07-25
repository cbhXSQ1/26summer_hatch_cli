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
        system_prompt = f"""You are a helpful coding agent. You have access to the following tools:

{tools_desc}

## Response Rules

1. **If you need to use tools**, output ONLY a JSON array in a code block:
```json
[{{"tool_name": "...", "parameters": {{...}}}}]
```

2. **If no tools are needed** (e.g. answering a question, explaining something, or the task is complete), write your response as normal text BEFORE the empty JSON block. Example:

Here is your answer. The function works correctly.
```json
[]
```

3. **Always provide helpful text** — explain what you're doing, what you found, or why you can't do something. Never output only an empty JSON block with no text.

4. When you modify files, run the tests afterwards to verify correctness."""

        if memory:
            system_prompt += f"\n\nProject context:\n{memory}"

        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        if feedback:
            messages.append({"role": "user", "content": f"Previous attempt feedback:\n{feedback}"})

        messages.append({"role": "user", "content": task})

        return messages
