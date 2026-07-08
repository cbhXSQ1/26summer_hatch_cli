"""测试数据模型

验证 SPEC §6 中定义的所有 dataclass 和枚举的正确性。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from hatch.core.models import (
    Action,
    ClassifiedFailure,
    FailureCategory,
    FeedbackSummary,
    GuardrailResult,
    LintIssue,
    LintResult,
    LoopState,
    MemoryEntry,
    TestError,
    TestResult,
    ToolResult,
    TypeCheckError,
    TypeCheckResult,
)


# ---------------------------------------------------------------------------
# FailureCategory 枚举
# ---------------------------------------------------------------------------

class TestFailureCategory:
    """FailureCategory 枚举测试"""

    def test_enum_values(self):
        """验证枚举值正确"""
        assert FailureCategory.SYNTAX_ERROR.value == 1
        assert FailureCategory.TYPE_ERROR.value == 2
        assert FailureCategory.LOGIC_ERROR.value == 3
        assert FailureCategory.RUNTIME_ERROR.value == 4
        assert FailureCategory.STYLE_ISSUE.value == 5
        assert FailureCategory.UNKNOWN.value == 6

    def test_enum_is_six_categories(self):
        """验证有 6 个类别"""
        assert len(FailureCategory) == 6

    def test_priority_ordering(self):
        """验证优先级排序：SYNTAX_ERROR 最高，UNKNOWN 最低"""
        assert FailureCategory.SYNTAX_ERROR < FailureCategory.TYPE_ERROR
        assert FailureCategory.TYPE_ERROR < FailureCategory.LOGIC_ERROR
        assert FailureCategory.LOGIC_ERROR < FailureCategory.RUNTIME_ERROR
        assert FailureCategory.RUNTIME_ERROR < FailureCategory.STYLE_ISSUE
        assert FailureCategory.STYLE_ISSUE < FailureCategory.UNKNOWN

    def test_sortable(self):
        """验证可按优先级排序"""
        categories = [
            FailureCategory.STYLE_ISSUE,
            FailureCategory.SYNTAX_ERROR,
            FailureCategory.UNKNOWN,
            FailureCategory.LOGIC_ERROR,
        ]
        sorted_cats = sorted(categories)
        assert sorted_cats == [
            FailureCategory.SYNTAX_ERROR,
            FailureCategory.LOGIC_ERROR,
            FailureCategory.STYLE_ISSUE,
            FailureCategory.UNKNOWN,
        ]


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

class TestAction:
    """Action 数据类测试"""

    def test_create_with_required_fields(self):
        action = Action(tool_name="file_reader", parameters={"path": "app.py"})
        assert action.tool_name == "file_reader"
        assert action.parameters == {"path": "app.py"}

    def test_default_raw_llm_output(self):
        action = Action(tool_name="shell_executor", parameters={"cmd": "ls"})
        assert action.raw_llm_output == ""

    def test_with_raw_llm_output(self):
        action = Action(
            tool_name="shell_executor",
            parameters={"cmd": "pytest"},
            raw_llm_output='{"tool": "shell_executor", "params": {"cmd": "pytest"}}',
        )
        assert action.raw_llm_output != ""


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------

class TestToolResult:
    """ToolResult 数据类测试"""

    def test_success_result(self):
        result = ToolResult(success=True, output="hello world")
        assert result.success is True
        assert result.output == "hello world"
        assert result.error is None
        assert result.exit_code is None

    def test_failure_result(self):
        result = ToolResult(
            success=False, error="command not found", exit_code=127
        )
        assert result.success is False
        assert result.error == "command not found"
        assert result.exit_code == 127

    def test_defaults(self):
        result = ToolResult(success=True)
        assert result.output == ""
        assert result.error is None
        assert result.exit_code is None


# ---------------------------------------------------------------------------
# TestError
# ---------------------------------------------------------------------------

class TestTestError:
    """TestError 数据类测试"""

    def test_create_with_required_fields(self):
        error = TestError(
            test_name="test_add",
            error_type="AssertionError",
            message="assert 2 == 3",
            file_path="tests/test_math.py",
        )
        assert error.test_name == "test_add"
        assert error.error_type == "AssertionError"
        assert error.message == "assert 2 == 3"
        assert error.file_path == "tests/test_math.py"

    def test_default_optionals(self):
        error = TestError(
            test_name="test_sub",
            error_type="NameError",
            message="name 'x' is not defined",
            file_path="tests/test_math.py",
        )
        assert error.line_number is None
        assert error.expected is None
        assert error.actual is None

    def test_with_expected_actual(self):
        error = TestError(
            test_name="test_add",
            error_type="AssertionError",
            message="assert 2 == 3",
            file_path="tests/test_math.py",
            line_number=15,
            expected="2",
            actual="3",
        )
        assert error.line_number == 15
        assert error.expected == "2"
        assert error.actual == "3"


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------

class TestTestResult:
    """TestResult 数据类测试"""

    def test_all_passed(self):
        result = TestResult(total=5, passed=5, failed=0)
        assert result.total == 5
        assert result.passed == 5
        assert result.failed == 0
        assert result.errors == []

    def test_with_failures(self):
        errors = [
            TestError(
                test_name="test_a",
                error_type="AssertionError",
                message="assert 1 == 2",
                file_path="test_x.py",
            ),
        ]
        result = TestResult(total=3, passed=1, failed=2, errors=errors)
        assert result.total == 3
        assert result.passed == 1
        assert result.failed == 2
        assert len(result.errors) == 1

    def test_defaults(self):
        result = TestResult()
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.errors == []


# ---------------------------------------------------------------------------
# LintIssue
# ---------------------------------------------------------------------------

class TestLintIssue:
    """LintIssue 数据类测试"""

    def test_create(self):
        issue = LintIssue(
            file_path="app.py",
            line=10,
            column=80,
            code="E501",
            message="line too long (89 > 79 characters)",
        )
        assert issue.file_path == "app.py"
        assert issue.line == 10
        assert issue.column == 80
        assert issue.code == "E501"
        assert issue.message == "line too long (89 > 79 characters)"


# ---------------------------------------------------------------------------
# LintResult
# ---------------------------------------------------------------------------

class TestLintResult:
    """LintResult 数据类测试"""

    def test_empty(self):
        result = LintResult()
        assert result.issues == []

    def test_with_issues(self):
        issues = [
            LintIssue("app.py", 1, 1, "F401", "unused import"),
            LintIssue("app.py", 5, 80, "E501", "line too long"),
        ]
        result = LintResult(issues=issues)
        assert len(result.issues) == 2


# ---------------------------------------------------------------------------
# TypeCheckError
# ---------------------------------------------------------------------------

class TestTypeCheckError:
    """TypeCheckError 数据类测试"""

    def test_create_error(self):
        err = TypeCheckError(
            file_path="app.py",
            line=12,
            column=5,
            severity="error",
            message='Incompatible types in assignment (expression has type "int", variable has type "str")',
        )
        assert err.file_path == "app.py"
        assert err.line == 12
        assert err.column == 5
        assert err.severity == "error"
        assert "Incompatible types" in err.message

    def test_create_note(self):
        err = TypeCheckError(
            file_path="app.py",
            line=12,
            column=0,
            severity="note",
            message="See above for details",
        )
        assert err.severity == "note"


# ---------------------------------------------------------------------------
# TypeCheckResult
# ---------------------------------------------------------------------------

class TestTypeCheckResult:
    """TypeCheckResult 数据类测试"""

    def test_empty(self):
        result = TypeCheckResult()
        assert result.errors == []

    def test_with_errors(self):
        errors = [
            TypeCheckError("app.py", 10, 5, "error", "type mismatch"),
        ]
        result = TypeCheckResult(errors=errors)
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# ClassifiedFailure
# ---------------------------------------------------------------------------

class TestClassifiedFailure:
    """ClassifiedFailure 数据类测试"""

    def test_create(self):
        failure = ClassifiedFailure(
            category=FailureCategory.SYNTAX_ERROR,
            priority=1,
        )
        assert failure.category == FailureCategory.SYNTAX_ERROR
        assert failure.priority == 1
        assert failure.failures == []

    def test_with_test_errors(self):
        errors = [
            TestError(
                test_name="test_foo",
                error_type="NameError",
                message="name 'x' is not defined",
                file_path="test.py",
            ),
        ]
        failure = ClassifiedFailure(
            category=FailureCategory.RUNTIME_ERROR,
            failures=errors,
            priority=4,
        )
        assert len(failure.failures) == 1
        assert failure.failures[0].test_name == "test_foo"

    def test_default_priority(self):
        failure = ClassifiedFailure(category=FailureCategory.UNKNOWN)
        assert failure.priority == 5


# ---------------------------------------------------------------------------
# FeedbackSummary
# ---------------------------------------------------------------------------

class TestFeedbackSummary:
    """FeedbackSummary 数据类测试"""

    def test_all_success(self):
        summary = FeedbackSummary(success=True, round_number=1)
        assert summary.success is True
        assert summary.total_issues == 0
        assert summary.by_category == {}
        assert summary.top_issues == []
        assert summary.round_number == 1

    def test_with_failures(self):
        by_cat = {FailureCategory.LOGIC_ERROR: 2, FailureCategory.STYLE_ISSUE: 1}
        summary = FeedbackSummary(
            success=False,
            total_issues=3,
            by_category=by_cat,
            context_for_llm="2 test failures, 1 style issue",
            round_number=2,
        )
        assert summary.success is False
        assert summary.total_issues == 3
        assert summary.by_category[FailureCategory.LOGIC_ERROR] == 2
        assert summary.context_for_llm == "2 test failures, 1 style issue"

    def test_default_context_for_llm(self):
        summary = FeedbackSummary()
        assert summary.context_for_llm == ""


# ---------------------------------------------------------------------------
# GuardrailResult
# ---------------------------------------------------------------------------

class TestGuardrailResult:
    """GuardrailResult 数据类测试"""

    def test_allowed(self):
        result = GuardrailResult(allowed=True, reason="safe command")
        assert result.allowed is True
        assert result.requires_approval is False

    def test_blocked(self):
        result = GuardrailResult(
            allowed=False, reason="dangerous: rm -rf /", requires_approval=False
        )
        assert result.allowed is False
        assert result.reason == "dangerous: rm -rf /"

    def test_needs_approval(self):
        result = GuardrailResult(
            allowed=False, reason="requires HITL", requires_approval=True
        )
        assert result.requires_approval is True

    def test_defaults(self):
        result = GuardrailResult()
        assert result.allowed is True
        assert result.reason == ""
        assert result.requires_approval is False


# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------

class TestMemoryEntry:
    """MemoryEntry 数据类测试"""

    def test_create(self):
        entry = MemoryEntry(key="test_framework", value="pytest")
        assert entry.key == "test_framework"
        assert entry.value == "pytest"
        assert isinstance(entry.timestamp, datetime)

    def test_with_timestamp(self):
        ts = datetime(2026, 7, 8, 12, 0, 0)
        entry = MemoryEntry(key="code_style", value="pep8", timestamp=ts)
        assert entry.timestamp == ts


# ---------------------------------------------------------------------------
# LoopState
# ---------------------------------------------------------------------------

class TestLoopState:
    """LoopState 数据类测试"""

    def test_defaults(self):
        state = LoopState()
        assert state.round == 0
        assert state.max_rounds == 3
        assert state.history == []
        assert state.status == "running"

    def test_custom_max_rounds(self):
        state = LoopState(max_rounds=5)
        assert state.max_rounds == 5

    def test_status_values(self):
        # 验证四种状态值可设置
        state = LoopState(status="running")
        assert state.status == "running"

        state.status = "success"
        assert state.status == "success"

        state.status = "failed"
        assert state.status == "failed"

        state.status = "stopped"
        assert state.status == "stopped"

    def test_with_history(self):
        summary = FeedbackSummary(success=True, round_number=1)
        state = LoopState(round=2, history=[summary])
        assert state.round == 2
        assert len(state.history) == 1
        assert state.history[0].round_number == 1


# ---------------------------------------------------------------------------
# 数据类是不可变的（frozen=False 默认，但字段可修改）
# ---------------------------------------------------------------------------

class TestDataClassMutability:
    """验证 dataclass 字段可正常修改"""

    def test_action_mutable(self):
        action = Action(tool_name="test", parameters={})
        action.tool_name = "updated"
        assert action.tool_name == "updated"

    def test_tool_result_mutable(self):
        result = ToolResult(success=True)
        result.output = "new output"
        assert result.output == "new output"