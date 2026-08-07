"""T6.1: SessionMemory 测试"""

import json
from pathlib import Path

from hatch.memory.session import SessionMemory


class TestSessionMemory:
    """SessionMemory"""

    def test_set_and_get(self) -> None:
        mem = SessionMemory()
        mem.set("framework", "pytest")
        assert mem.get("framework") == "pytest"

    def test_get_nonexistent(self) -> None:
        mem = SessionMemory()
        assert mem.get("nonexistent") is None

    def test_get_all(self) -> None:
        mem = SessionMemory()
        mem.set("a", "1")
        mem.set("b", "2")
        all_entries = mem.get_all()
        assert all_entries["a"] == "1"
        assert all_entries["b"] == "2"

    def test_max_entries(self) -> None:
        mem = SessionMemory(max_entries=3)
        mem.set("k1", "v1")
        mem.set("k2", "v2")
        mem.set("k3", "v3")
        mem.set("k4", "v4")  # should be rejected
        assert mem.get("k4") is None
        assert len(mem.get_all()) == 3

    def test_truncates_long_value(self) -> None:
        mem = SessionMemory(max_value_len=10)
        mem.set("key", "a" * 20)
        assert len(mem.get("key")) == 10

    def test_persist_and_restore(self, tmp_path) -> None:
        path = tmp_path / "memory.json"
        mem = SessionMemory(persist_path=str(path))
        mem.set("topic", "testing")
        mem.save()

        mem2 = SessionMemory(persist_path=str(path))
        mem2.load()
        assert mem2.get("topic") == "testing"

    def test_corrupted_json_graceful(self, tmp_path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        mem = SessionMemory(persist_path=str(path))
        mem.load()  # should not raise
        assert mem.get_all() == {}

    def test_get_relevant_context_matching_query(self) -> None:
        mem = SessionMemory()
        mem.set("framework", "pytest")
        mem.set("language", "python")
        result = mem.get_relevant_context("pytest")
        assert "framework: pytest" in result

    def test_get_relevant_context_no_match(self) -> None:
        mem = SessionMemory()
        mem.set("key", "value")
        result = mem.get_relevant_context("nonexistent")
        assert result == ""

    def test_save_with_empty_persist_path(self, tmp_path) -> None:
        mem = SessionMemory(persist_path="")
        mem.set("topic", "testing")
        mem.save()

    def test_load_with_empty_persist_path(self) -> None:
        mem = SessionMemory(persist_path="")
        mem.load()

    def test_load_file_not_exists(self, tmp_path) -> None:
        mem = SessionMemory(persist_path=str(tmp_path / "nonexistent.json"))
        mem.load()
        assert mem.get_all() == {}

    def test_get_relevant_context_case_insensitive(self) -> None:
        mem = SessionMemory()
        mem.set("Task", "Python")
        result = mem.get_relevant_context("python")
        assert "Task: Python" in result


class TestSessionManager:
    def test_rename_session(self, tmp_path):
        from hatch.memory.session_manager import SessionManager
        sm = SessionManager(str(tmp_path))
        sid = sm.create("original")
        sm.rename(sid, "renamed")
        info = sm.get_info(sid)
        assert info["task"] == "renamed"

    def test_get_conversation_turns_limit_none_returns_all(self, tmp_path):
        from hatch.memory.session_manager import SessionManager
        sm = SessionManager(str(tmp_path))
        sid = sm.create("t")
        for i in range(15):
            sm.add_conversation_turn(sid, "user", f"msg {i}")
        all_turns = sm.get_conversation_turns(sid, limit=None)
        assert len(all_turns) == 15
        assert all_turns[0]["content"] == "msg 0"
        limited = sm.get_conversation_turns(sid, limit=5)
        assert len(limited) == 5
        assert limited[0]["content"] == "msg 10"