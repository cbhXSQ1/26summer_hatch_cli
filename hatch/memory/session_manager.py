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
        self.config_path = self.hatch_dir / "config.yaml"

    def _ensure_dirs(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _read_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, encoding="utf-8") as f:
            return json.loads(f.read())

    def _write_config(self, data: dict) -> None:
        self.hatch_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

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
            json.dumps({"meta": entry, "history": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._write_config({"active_session": session_id})
        return session_id

    def activate(self, session_id: str) -> None:
        index = self._read_index()
        if not any(e["id"] == session_id for e in index):
            raise ValueError(f"会话 {session_id} 不存在")

        self._write_config({"active_session": session_id})

    def get_active(self) -> str | None:
        config = self._read_config()
        sid = config.get("active_session")
        if sid is None:
            return None

        index = self._read_index()
        if not any(e["id"] == sid for e in index):
            return None
        return sid

    def get_info(self, session_id: str | None = None) -> dict | None:
        if session_id is None:
            session_id = self.get_active()
        if session_id is None:
            return None

        index = self._read_index()
        for e in index:
            if e["id"] == session_id:
                return e
        return None

    def list_sessions(self) -> list[dict]:
        return self._read_index()

    def get_active_or_create(self, task: str) -> tuple[str, bool]:
        existing = self.get_active()
        if existing:
            return existing, False
        return self.create(task), True

    def update_status(self, session_id: str, rounds: int, status: str) -> None:
        index = self._read_index()
        for e in index:
            if e["id"] == session_id:
                e["updated"] = datetime.now().isoformat()
                e["rounds"] = rounds
                e["status"] = status
                break
        self._write_index(index)

    def save_history(self, session_id: str, history_data: list[dict]) -> None:
        path = self._session_path(session_id)
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {"meta": {}, "history": []}
        else:
            existing = {"meta": {}, "history": []}

        existing["history"] = history_data
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
