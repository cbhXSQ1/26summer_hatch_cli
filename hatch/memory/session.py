"""会话记忆"""

import json
from pathlib import Path


class SessionMemory:
    """会话记忆存储"""

    def __init__(
        self,
        max_entries: int = 100,
        max_value_len: int = 4096,
        persist_path: str = "",
    ) -> None:
        self.max_entries = max_entries
        self.max_value_len = max_value_len
        self.persist_path = persist_path
        self._data: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        if len(self._data) >= self.max_entries and key not in self._data:
            return
        if len(value) > self.max_value_len:
            value = value[:self.max_value_len]
        self._data[key] = value

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def get_all(self) -> dict[str, str]:
        return dict(self._data)

    def get_relevant_context(self, query: str) -> str:
        parts: list[str] = []
        for k, v in self._data.items():
            if query.lower() in k.lower() or query.lower() in v.lower():
                parts.append(f"{k}: {v}")
        return "\n".join(parts)

    def save(self) -> None:
        if not self.persist_path:
            return
        path = Path(self.persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")

    def load(self) -> None:
        if not self.persist_path:
            return
        path = Path(self.persist_path)
        if not path.exists():
            return
        try:
            self._data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._data = {}