"""T5.8: FeedbackEngine 集成测试"""

from hatch.core.models import Action, ToolResult
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