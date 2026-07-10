"""反馈引擎主入口"""

from hatch.core.models import Action, ToolResult, FeedbackSummary
from hatch.feedback.parsers.test_parser import TestResultParser
from hatch.feedback.parsers.lint_parser import LintResultParser
from hatch.feedback.parsers.type_parser import TypeCheckParser
from hatch.feedback.aggregator import FeedbackAggregator


class FeedbackEngine:
    """统一的反馈引擎"""

    def __init__(self) -> None:
        self._history: list[FeedbackSummary] = []

    def process(self, action: Action, result: ToolResult, round_number: int) -> FeedbackSummary:
        if not result.success and result.error:
            summary = FeedbackSummary(
                success=False,
                total_issues=1,
                context_for_llm=f"执行失败: {result.error}",
                round_number=round_number,
            )
            self._history.append(summary)
            if self.is_stuck():
                summary.context_for_llm += "\n\n注意: 连续两轮反馈相同，请尝试不同的修正方法。"
            return summary

        if action.tool_name == "test_runner":
            test_result = TestResultParser.parse(result.output)
            lint_result = LintResultParser().parse("")
            type_result = TypeCheckParser().parse("")
        elif action.tool_name == "linter":
            test_result = TestResultParser.parse("")
            lint_result = LintResultParser().parse(result.output)
            type_result = TypeCheckParser().parse("")
        elif action.tool_name == "type_checker":
            test_result = TestResultParser.parse("")
            lint_result = LintResultParser().parse("")
            type_result = TypeCheckParser().parse(result.output)
        else:
            test_result = TestResultParser.parse(result.output or "")
            lint_result = LintResultParser().parse(result.output or "")
            type_result = TypeCheckParser().parse(result.output or "")

        summary = FeedbackAggregator.aggregate(
            test_result, lint_result, type_result, round_number,
        )

        self._history.append(summary)
        if self.is_stuck():
            summary.context_for_llm += "\n\n注意: 连续两轮反馈相同，请尝试不同的修正方法。"
        return summary

    def is_stuck(self) -> bool:
        if len(self._history) < 2:
            return False
        prev = self._history[-1]
        if prev.total_issues > 0 and prev.total_issues == self._history[-2].total_issues:
            prev_cats = dict(prev.by_category)
            last_cats = dict(self._history[-2].by_category)
            if prev_cats == last_cats:
                return True
        return False