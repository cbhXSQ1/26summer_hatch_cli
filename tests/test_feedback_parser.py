"""T5.2–T5.4: 反馈解析器 测试"""

import pytest
from hatch.feedback.parsers.test_parser import TestResultParser
from hatch.feedback.parsers.lint_parser import LintResultParser
from hatch.feedback.parsers.type_parser import TypeCheckParser


class TestTestResultParser:
    """TestResultParser"""

    def test_parses_pytest_output(self) -> None:
        text = """============================= test session starts =============================
collected 5 items

tests/test_calc.py::test_add PASSED
tests/test_calc.py::test_multiply FAILED
tests/test_calc.py::test_divide PASSED

=================================== FAILURES ===================================
_____________ test_multiply ______________

    def test_multiply():
>       assert multiply(2, 3) == 6
E       assert 5 == 6

tests/test_calc.py:12: AssertionError
========================= 1 failed, 2 passed in 0.12s ========================="""
        result = TestResultParser.parse(text)
        assert result.total == 3
        assert result.passed == 2
        assert result.failed == 1
        assert len(result.errors) == 1
        assert result.errors[0].test_name == "test_multiply"
        assert result.errors[0].error_type == "AssertionError"

    def test_all_passed(self) -> None:
        text = """collected 3 items
tests/test_x.py::test_a PASSED
tests/test_x.py::test_b PASSED
tests/test_x.py::test_c PASSED
3 passed"""
        result = TestResultParser.parse(text)
        assert result.total == 3
        assert result.passed == 3
        assert result.failed == 0


class TestLintResultParser:
    """LintResultParser"""

    def test_parses_flake8_output(self) -> None:
        text = """app.py:15:80: E501 line too long
app.py:3:1: F401 'os' imported but unused"""
        result = LintResultParser.parse(text)
        assert len(result.issues) == 2
        assert result.issues[0].file_path == "app.py"
        assert result.issues[0].line == 15
        assert result.issues[0].code == "E501"
        assert result.issues[1].code == "F401"

    def test_empty_output(self) -> None:
        result = LintResultParser.parse("")
        assert result.issues == []


class TestTypeCheckParser:
    """TypeCheckParser"""

    def test_parses_mypy_output(self) -> None:
        text = """app.py:10: error: Incompatible return value type
app.py:10: note: Perhaps you meant to use "int()" ?"""
        result = TypeCheckParser.parse(text)
        assert len(result.errors) == 2
        assert result.errors[0].severity == "error"
        assert result.errors[1].severity == "note"

    def test_empty_output(self) -> None:
        result = TypeCheckParser.parse("")
        assert result.errors == []