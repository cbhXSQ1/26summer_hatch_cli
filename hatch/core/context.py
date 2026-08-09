"""上下文组装器"""


class ContextBuilder:
    """组装发送给 LLM 的消息上下文"""

    @staticmethod
    def build(
        task: str,
        tools_desc: str,
        feedback: str = "",
        memory: str = "",
        conversation_history: list[dict] | None = None,
        observations: str = "",
        workdir: str = "",
    ) -> list[dict]:
        system_prompt = f"""You are a helpful coding agent. You have access to the following tools:

{tools_desc}

## Working Directory

The current working directory is: {workdir}

All relative paths in tool parameters are relative to this directory.
Do NOT assume any other directory — always trust the working directory above,
even if previous conversation messages mention other paths.

## Environment

Operating system: Windows, shell is cmd.exe (NOT PowerShell).
Use Windows cmd commands only: `dir`, `type`, `findstr`, `cd`, `echo`.
Do NOT use PowerShell-only commands (e.g. `Get-ChildItem`, `ls`, `pwd`, `Select-Object`).
List directories with `dir /b` one level at a time.
Do NOT run `dir /s /b` on the whole repository — it floods the output with
`.git`, `venv`, `__pycache__` and other internal files. Use targeted commands
like `dir /b hatch` instead.

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

4. When you modify files, run the tests afterwards to verify correctness.

5. **Every response MUST end with a ```json code block** containing the tool-call array (or ```json [] ``` when you have nothing more to do). NEVER respond with plain text only — if you say you will do something (e.g. "我先...", "接下来调用..."), you must actually call the tool in the same response."""

        if memory:
            system_prompt += f"\n\nProject context:\n{memory}"

        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        if memory:
            messages.append({"role": "user", "content": f"Project context:\n{memory}"})

        if conversation_history:
            for turn in conversation_history:
                messages.append({"role": turn["role"], "content": turn["content"]})

        if observations:
            messages.append({
                "role": "user",
                "content": (
                    "上一轮工具执行结果（请基于这些结果继续任务，"
                    "不要重复执行相同命令）：\n"
                    f"{observations}"
                ),
            })

        if feedback:
            messages.append({"role": "user", "content": f"Previous attempt feedback:\n{feedback}"})

        messages.append({"role": "user", "content": task})

        return messages
