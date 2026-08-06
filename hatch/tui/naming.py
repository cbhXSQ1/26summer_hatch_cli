"""Auto-name a conversation via low-temperature LLM call."""

from hatch.core.llm import LLMBackend


def auto_name(task: str, first_reply: str, llm: LLMBackend, max_chars: int = 20) -> str:
    prompt = (
        f"给这段对话起一个简短名字（{max_chars}字以内，只返回名字不要解释）：\n"
        f"用户：{task[:100]}\n"
        f"助手：{first_reply[:200]}"
    )
    messages = [{"role": "user", "content": prompt}]
    try:
        name = llm.complete(messages, temperature=0.0).strip()
        name = name.strip('"\' \n')
        if len(name) > max_chars:
            name = name[:max_chars]
        return name or task[:max_chars]
    except Exception:
        return task[:max_chars]
