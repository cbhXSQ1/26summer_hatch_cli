# tests/test_tui_naming.py
from unittest.mock import MagicMock
from hatch.tui.naming import auto_name


class TestAutoName:
    def test_returns_string(self):
        llm = MagicMock()
        llm.complete.return_value = "修复bug"
        result = auto_name("help fix test", "let me check", llm)
        assert isinstance(result, str)
        assert len(result) > 0
        assert len(result) <= 20

    def test_truncates_long_name(self):
        llm = MagicMock()
        llm.complete.return_value = "a" * 50
        result = auto_name("t", "r", llm)
        assert len(result) <= 20

    def test_calls_with_temperature_0(self):
        llm = MagicMock()
        llm.complete.return_value = "x"
        auto_name("task", "reply", llm)
        call_args = llm.complete.call_args
        assert call_args[1].get("temperature") == 0.0
