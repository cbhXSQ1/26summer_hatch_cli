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