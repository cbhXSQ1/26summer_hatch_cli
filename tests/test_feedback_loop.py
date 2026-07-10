"""T5.8: FeedbackEngine 集成测试"""

from hatch.core.models import Action, FeedbackSummary, ToolResult
from hatch.feedback.engine import FeedbackEngine


class TestFeedbackEngine:
    """FeedbackEngine"""

    def test_processes_test_runner_action(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="test_runner", parameters={})
        result = ToolResult(
            success=False, exit_code=1,
            output="""collected 3 items
test_a PASSED
test_b FAILED
test_c PASSED
======================= FAILURES =======================
_____________ test_b _____________
    def test_b():
>       assert 1 == 2
E       assert 1 == 2
1 failed, 2 passed""",
        )
        summary = engine.process(action, result, round_number=1)
        assert summary.success is False
        assert summary.total_issues > 0
        assert summary.round_number == 1

    def test_processes_linter_action(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="linter", parameters={})
        result = ToolResult(
            success=False, exit_code=1,
            output="app.py:15:80: E501 line too long",
        )
        summary = engine.process(action, result, round_number=1)
        assert summary.total_issues > 0

    def test_all_pass_is_success(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="test_runner", parameters={})
        result = ToolResult(
            success=True, exit_code=0,
            output="3 passed",
        )
        summary = engine.process(action, result, round_number=1)
        assert summary.success is True

    def test_loop_detection(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="test_runner", parameters={})
        result = ToolResult(
            success=False, exit_code=1,
            output="""collected 1 items
test_x FAILED
======================= FAILURES =======================
_____________ test_x _____________
    def test_x():
>       assert 1 == 2
E       assert 1 == 2
1 failed""",
        )
        summary1 = engine.process(action, result, round_number=1)
        summary2 = engine.process(action, result, round_number=2)
        assert engine.is_stuck() is True
        assert "尝试" in summary2.context_for_llm

    def test_processes_type_checker_action(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="type_checker", parameters={})
        result = ToolResult(
            success=False, exit_code=1,
            output="""app.py:10: error: Incompatible return value type
app.py:15: error: Name 'x' is not defined""",
        )
        summary = engine.process(action, result, round_number=1)
        assert summary.total_issues > 0

    def test_processes_unrecognized_tool_action(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="unknown_tool", parameters={})
        result = ToolResult(
            success=False, exit_code=1,
            output="some random output from unknown tool",
        )
        summary = engine.process(action, result, round_number=1)
        assert summary is not None

    def test_processes_tool_failure_with_error(self) -> None:
        engine = FeedbackEngine()
        action = Action(tool_name="test_runner", parameters={})
        result = ToolResult(
            success=False, exit_code=1,
            error="some error message",
        )
        summary = engine.process(action, result, round_number=1)
        assert summary.success is False
        assert "some error message" in summary.context_for_llm

    def test_is_stuck_different_total_issues(self) -> None:
        engine = FeedbackEngine()
        engine._history = [
            FeedbackSummary(success=False, total_issues=1, round_number=1),
            FeedbackSummary(success=False, total_issues=2, round_number=2),
        ]
        assert engine.is_stuck() is False

    def test_is_stuck_same_issues_different_categories(self) -> None:
        from hatch.core.models import FailureCategory

        engine = FeedbackEngine()
        engine._history = [
            FeedbackSummary(
                success=False, total_issues=2, round_number=1,
                by_category={FailureCategory.TYPE_ERROR: 2},
            ),
            FeedbackSummary(
                success=False, total_issues=2, round_number=2,
                by_category={FailureCategory.LOGIC_ERROR: 2},
            ),
        ]
        assert engine.is_stuck() is False

    def test_is_stuck_less_than_two_entries(self) -> None:
        engine = FeedbackEngine()
        engine._history = [
            FeedbackSummary(success=False, total_issues=1, round_number=1),
        ]
        assert engine.is_stuck() is False