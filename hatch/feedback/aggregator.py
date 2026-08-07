"""反馈聚合器"""

from hatch.core.models import (
    TestResult, LintResult, TypeCheckResult,
    FeedbackSummary, FailureCategory,
)
from hatch.feedback.classifier import FailureClassifier
from hatch.feedback.strategies import CorrectionStrategySelector


class FeedbackAggregator:

    @staticmethod
    def aggregate(
        test_result: TestResult,
        lint_result: LintResult,
        type_result: TypeCheckResult,
        round_number: int,
    ) -> FeedbackSummary:
        failures = FailureClassifier.classify(test_result, lint_result, type_result)
        total_issues = len(failures)
        success = total_issues == 0

        by_category: dict[FailureCategory, int] = {}
        for f in failures:
            by_category[f.category] = by_category.get(f.category, 0) + 1

        top_issues = failures[:5]

        parts: list[str] = []
        if success:
            parts.append("执行成功，未发现问题。")
        else:
            parts.append(f"发现 {total_issues} 个问题:")
            for f in top_issues:
                strategy = CorrectionStrategySelector.select(f)
                parts.append(f"  - {strategy}")

        context_for_llm = "\n".join(parts)

        return FeedbackSummary(
            success=success,
            total_issues=total_issues,
            by_category=by_category,
            top_issues=top_issues,
            context_for_llm=context_for_llm,
            round_number=round_number,
        )