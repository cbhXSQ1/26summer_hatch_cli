"""修正策略选择器"""

from hatch.core.models import ClassifiedFailure, FailureCategory


class CorrectionStrategySelector:

    @staticmethod
    def select(failure: ClassifiedFailure) -> str:
        cat = failure.category
        if cat == FailureCategory.SYNTAX_ERROR:
            err = failure.failures[0]
            return (
                f"[语法错误] 文件 {err.file_path}:{err.line_number} 处存在语法错误: "
                f"{err.message}\n请修正语法错误。"
            )

        if cat == FailureCategory.TYPE_ERROR:
            err = failure.failures[0]
            return (
                f"[类型错误] 文件 {err.file_path}:{err.line}: "
                f"{err.message}\n请修正类型不匹配。"
            )

        if cat == FailureCategory.LOGIC_ERROR:
            err = failure.failures[0]
            parts = [f"[逻辑错误] 测试 {err.test_name} 断言失败"]
            if err.expected and err.actual:
                parts.append(f"期望值: {err.expected}, 实际值: {err.actual}")
            parts.append(f"错误: {err.message}")
            return "\n".join(parts)

        if cat == FailureCategory.RUNTIME_ERROR:
            err = failure.failures[0]
            return (
                f"[运行时错误] {err.error_type}: {err.message}\n"
                f"请修正运行时异常。"
            )

        if cat == FailureCategory.STYLE_ISSUE:
            err = failure.failures[0]
            return (
                f"[代码风格] 文件 {err.file_path}:{err.line} "
                f"违反规则 {err.code}: {err.message}"
            )

        return f"[未知问题] {failure.failures[0]}"