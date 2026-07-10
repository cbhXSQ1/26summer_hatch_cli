"""失败分类器"""

from hatch.core.models import (
    TestResult, LintResult, TypeCheckResult,
    ClassifiedFailure, FailureCategory,
)


class FailureClassifier:

    @staticmethod
    def classify(
        test_result: TestResult,
        lint_result: LintResult,
        type_result: TypeCheckResult,
    ) -> list[ClassifiedFailure]:
        failures: list[ClassifiedFailure] = []

        for err in test_result.errors:
            if err.error_type in ("SyntaxError", "IndentationError"):
                failures.append(ClassifiedFailure(
                    category=FailureCategory.SYNTAX_ERROR,
                    failures=[err],
                    priority=FailureCategory.SYNTAX_ERROR.value,
                ))
            elif err.error_type == "AssertionError":
                failures.append(ClassifiedFailure(
                    category=FailureCategory.LOGIC_ERROR,
                    failures=[err],
                    priority=FailureCategory.LOGIC_ERROR.value,
                ))
            else:
                failures.append(ClassifiedFailure(
                    category=FailureCategory.RUNTIME_ERROR,
                    failures=[err],
                    priority=FailureCategory.RUNTIME_ERROR.value,
                ))

        # 如果有 failed 计数但没有详细 error 对象，补充合成失败
        if test_result.failed > len(test_result.errors):
            from hatch.core.models import TestError
            missing = test_result.failed - len(test_result.errors)
            for i in range(missing):
                synthetic_err = TestError(
                    test_name=f"test_{i+1}",
                    error_type="Unknown",
                    message="测试失败（未解析到详情）",
                    file_path="",
                )
                failures.append(ClassifiedFailure(
                    category=FailureCategory.RUNTIME_ERROR,
                    failures=[synthetic_err],
                    priority=FailureCategory.RUNTIME_ERROR.value,
                ))

        for issue in lint_result.issues:
            failures.append(ClassifiedFailure(
                category=FailureCategory.STYLE_ISSUE,
                failures=[issue],
                priority=FailureCategory.STYLE_ISSUE.value,
            ))

        for err in type_result.errors:
            if err.severity == "error":
                failures.append(ClassifiedFailure(
                    category=FailureCategory.TYPE_ERROR,
                    failures=[err],
                    priority=FailureCategory.TYPE_ERROR.value,
                ))

        failures.sort(key=lambda f: f.priority)
        return failures