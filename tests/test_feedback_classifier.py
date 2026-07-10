"""T5.5: FailureClassifier 测试"""

from hatch.core.models import (
    TestResult, TestError, LintResult, LintIssue,
    TypeCheckResult, TypeCheckError, FailureCategory,
    ClassifiedFailure,
)
from hatch.feedback.classifier import FailureClassifier


class TestFailureClassifier:
    """FailureClassifier"""

    def test_classifies_syntax_error(self) -> None:
        test_result = TestResult(
            total=1, failed=1,
            errors=[TestError(
                test_name="test_import",
                error_type="SyntaxError",
                message="invalid syntax",
                file_path="app.py",
                line_number=5,
            )],
        )
        failures = FailureClassifier.classify(test_result, LintResult(), TypeCheckResult())
        assert len(failures) == 1
        assert failures[0].category == FailureCategory.SYNTAX_ERROR
        assert failures[0].priority == 1

    def test_classifies_type_error(self) -> None:
        type_result = TypeCheckResult(
            errors=[TypeCheckError(
                file_path="app.py", line=10, column=0,
                severity="error", message="Incompatible types",
            )],
        )
        failures = FailureClassifier.classify(TestResult(), LintResult(), type_result)
        assert failures[0].category == FailureCategory.TYPE_ERROR
        assert failures[0].priority == 2

    def test_classifies_logic_error(self) -> None:
        test_result = TestResult(
            total=1, failed=1,
            errors=[TestError(
                test_name="test_add", error_type="AssertionError",
                message="assert 5 == 6", file_path="test_calc.py",
            )],
        )
        failures = FailureClassifier.classify(test_result, LintResult(), TypeCheckResult())
        assert failures[0].category == FailureCategory.LOGIC_ERROR
        assert failures[0].priority == 3

    def test_classifies_style_issue(self) -> None:
        lint_result = LintResult(
            issues=[LintIssue(
                file_path="app.py", line=15, column=80, code="E501",
                message="line too long",
            )],
        )
        failures = FailureClassifier.classify(TestResult(), lint_result, TypeCheckResult())
        assert failures[0].category == FailureCategory.STYLE_ISSUE
        assert failures[0].priority == 5

    def test_empty_input(self) -> None:
        failures = FailureClassifier.classify(TestResult(), LintResult(), TypeCheckResult())
        assert failures == []

    def test_sorts_by_priority(self) -> None:
        test_result = TestResult(
            total=2, failed=2,
            errors=[
                TestError(test_name="t1", error_type="AssertionError", message="", file_path=""),
                TestError(test_name="t2", error_type="SyntaxError", message="", file_path=""),
            ],
        )
        failures = FailureClassifier.classify(test_result, LintResult(), TypeCheckResult())
        assert failures[0].category == FailureCategory.SYNTAX_ERROR
        assert failures[1].category == FailureCategory.LOGIC_ERROR


class TestCorrectionStrategySelector:
    """CorrectionStrategySelector"""

    def test_syntax_error_strategy(self) -> None:
        from hatch.feedback.strategies import CorrectionStrategySelector

        cf = ClassifiedFailure(
            category=FailureCategory.SYNTAX_ERROR,
            failures=[TestError(
                test_name="t", error_type="SyntaxError",
                message="invalid syntax", file_path="app.py", line_number=5,
            )],
            priority=1,
        )
        text = CorrectionStrategySelector.select(cf)
        assert "app.py" in text
        assert "5" in text
        assert "syntax" in text.lower()

    def test_logic_error_strategy(self) -> None:
        from hatch.feedback.strategies import CorrectionStrategySelector

        cf = ClassifiedFailure(
            category=FailureCategory.LOGIC_ERROR,
            failures=[TestError(
                test_name="test_add", error_type="AssertionError",
                message="assert 5 == 6", file_path="test_calc.py",
                expected="6", actual="5",
            )],
            priority=3,
        )
        text = CorrectionStrategySelector.select(cf)
        assert "test_add" in text
        assert "6" in text
        assert "5" in text

    def test_style_strategy(self) -> None:
        from hatch.feedback.strategies import CorrectionStrategySelector

        cf = ClassifiedFailure(
            category=FailureCategory.STYLE_ISSUE,
            failures=[LintIssue(
                file_path="app.py", line=15, column=80, code="E501",
                message="line too long",
            )],
            priority=5,
        )
        text = CorrectionStrategySelector.select(cf)
        assert "E501" in text


class TestFeedbackAggregator:
    """FeedbackAggregator"""

    def test_all_success(self) -> None:
        from hatch.feedback.aggregator import FeedbackAggregator

        summary = FeedbackAggregator.aggregate(TestResult(), LintResult(), TypeCheckResult(), 1)
        assert summary.success is True
        assert summary.total_issues == 0
        assert summary.round_number == 1

    def test_with_failures(self) -> None:
        from hatch.feedback.aggregator import FeedbackAggregator

        test_result = TestResult(
            total=1, failed=1,
            errors=[TestError(
                test_name="t", error_type="AssertionError",
                message="assert 5 == 6", file_path="test.py",
            )],
        )
        summary = FeedbackAggregator.aggregate(test_result, LintResult(), TypeCheckResult(), 2)
        assert summary.success is False
        assert summary.total_issues > 0
        assert len(summary.context_for_llm) > 0

    def test_top_issues_limited_to_5(self) -> None:
        from hatch.feedback.aggregator import FeedbackAggregator

        lint = LintResult(issues=[LintIssue(
            file_path=f"f{i}.py", line=i, column=0, code="E501", message="long"
        ) for i in range(10)])
        summary = FeedbackAggregator.aggregate(TestResult(), lint, TypeCheckResult(), 1)
        assert len(summary.top_issues) <= 5