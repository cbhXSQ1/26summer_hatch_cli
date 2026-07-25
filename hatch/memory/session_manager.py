"""会话管理器：在 .hatch/ 目录下持久化多轮对话"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path


class SessionManager:

    def __init__(self, workdir: str | None = None) -> None:
        self.workdir = Path(workdir) if workdir else Path.cwd()
        self.hatch_dir = self.workdir / ".hatch"
        self.sessions_dir = self.hatch_dir / "sessions"

    def _ensure_dirs(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _read_index(self) -> list[dict]:
        index_path = self.sessions_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, encoding="utf-8") as f:
                return json.loads(f.read())
        except (json.JSONDecodeError, OSError):
            return []

    def _write_index(self, entries: list[dict]) -> None:
        self._ensure_dirs()
        index_path = self.sessions_dir / "index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def create(self, task: str) -> str:
        self._ensure_dirs()
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()

        entry = {
            "id": session_id,
            "task": task,
            "created": now,
            "updated": now,
            "rounds": 0,
            "status": "active",
        }

        index = self._read_index()
        index.append(entry)
        self._write_index(index)

        self._session_path(session_id).write_text(
            json.dumps({"meta": entry, "turns": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return session_id

    def get_latest(self) -> str | None:
        index = self._read_index()
        if not index:
            return None
        latest = max(index, key=lambda e: e.get("updated", ""))
        return latest["id"]

    def get_latest_or_create(self, task: str) -> tuple[str, bool]:
        existing = self.get_latest()
        if existing:
            return existing, False
        return self.create(task), True

    def get_info(self, session_id: str | None = None) -> dict | None:
        if session_id is None:
            session_id = self.get_latest()
        if session_id is None:
            return None
        index = self._read_index()
        for e in index:
            if e["id"] == session_id:
                return e
        return None

    def list_sessions(self) -> list[dict]:
        index = self._read_index()
        index.sort(key=lambda e: e.get("updated", ""), reverse=True)
        return index

    def update_status(self, session_id: str, rounds: int, status: str) -> None:
        index = self._read_index()
        for e in index:
            if e["id"] == session_id:
                e["updated"] = datetime.now().isoformat()
                e["rounds"] = rounds
                e["status"] = status
                break
        self._write_index(index)

    def get_conversation_turns(self, session_id: str, limit: int = 10) -> list[dict]:
        path = self._session_path(session_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            turns = data.get("turns", [])
            return turns[-limit:] if len(turns) > limit else turns
        except (json.JSONDecodeError, OSError):
            return []

    def add_conversation_turn(self, session_id: str, role: str, content: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {"meta": {}, "turns": []}
        else:
            data = {"meta": {}, "turns": []}
        data.setdefault("turns", []).append({
            "role": role,
            "content": content[:8000],
            "time": datetime.now().isoformat(),
        })
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_history(self, session_id: str, history_data: list[dict]) -> None:
        path = self._session_path(session_id)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {"meta": {}, "turns": []}
        else:
            data = {"meta": {}, "turns": []}
        data["history"] = history_data
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
