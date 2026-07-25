"""Hatch 核心数据模型

按 SPEC §6 定义所有共享的 dataclass 和枚举。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class FailureCategory(Enum):
    """失败类别枚举（按修正优先级排序）"""
    SYNTAX_ERROR = 1    # 语法错误（无法 import、SyntaxError）
    TYPE_ERROR = 2      # 类型不匹配
    LOGIC_ERROR = 3     # 测试断言失败（逻辑错误）
    RUNTIME_ERROR = 4   # 运行时异常（非语法/类型/逻辑）
    STYLE_ISSUE = 5     # 代码风格问题
    UNKNOWN = 6         # 无法归类

    def __lt__(self, other: "FailureCategory") -> bool:
        return self.value < other.value

    def __le__(self, other: "FailureCategory") -> bool:
        return self.value <= other.value

    def __gt__(self, other: "FailureCategory") -> bool:
        return self.value > other.value

    def __ge__(self, other: "FailureCategory") -> bool:
        return self.value >= other.value


# ---------------------------------------------------------------------------
# 核心实体
# ---------------------------------------------------------------------------

@dataclass
class Action:
    """LLM 决策产生的动作"""
    tool_name: str
    parameters: dict[str, Any]
    raw_llm_output: str = ""  # LLM 原始输出（用于调试）


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: str = ""
    error: str | None = None
    exit_code: int | None = None


# ---------------------------------------------------------------------------
# 测试结果
# ---------------------------------------------------------------------------

@dataclass
class TestError:
    """单个测试失败详情"""
    test_name: str
    error_type: str          # AssertionError | ImportError | NameError | ...
    message: str
    file_path: str
    line_number: int | None = None
    expected: str | None = None
    actual: str | None = None


@dataclass
class TestResult:
    """pytest 运行结果"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: list[TestError] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lint 结果
# ---------------------------------------------------------------------------

@dataclass
class LintIssue:
    """单个 lint 问题"""
    file_path: str
    line: int
    column: int
    code: str     # E501, F401, W291 ...
    message: str


@dataclass
class LintResult:
    """flake8 运行结果"""
    issues: list[LintIssue] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 类型检查结果
# ---------------------------------------------------------------------------

@dataclass
class TypeCheckError:
    """单个类型检查错误

    注意：命名为 TypeCheckError 而非 TypeError，避免与 Python 内置
    ``TypeError`` 异常冲突。
    """
    file_path: str
    line: int
    column: int
    severity: str   # "error" | "note"
    message: str


@dataclass
class TypeCheckResult:
    """mypy 运行结果"""
    errors: list[TypeCheckError] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 反馈相关
# ---------------------------------------------------------------------------

@dataclass
class ClassifiedFailure:
    """分类后的失败项"""
    category: FailureCategory
    failures: list[TestError | LintIssue | TypeCheckError] = field(default_factory=list)
    priority: int = 5  # 1-5，1 最高


@dataclass
class FeedbackSummary:
    """多源反馈聚合摘要"""
    success: bool = True                     # 是否全部通过
    total_issues: int = 0
    by_category: dict[FailureCategory, int] = field(default_factory=dict)
    top_issues: list[ClassifiedFailure] = field(default_factory=list)
    context_for_llm: str = ""                # 注入 LLM 上下文的格式化文本
    round_number: int = 0


# ---------------------------------------------------------------------------
# 护栏
# ---------------------------------------------------------------------------

@dataclass
class GuardrailResult:
    """护栏检查结果"""
    allowed: bool = True
    reason: str = ""
    requires_approval: bool = False


# ---------------------------------------------------------------------------
# 记忆
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """单条会话记忆"""
    key: str
    value: str
    timestamp: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# 循环状态
# ---------------------------------------------------------------------------

@dataclass
class LoopState:
    """Agent 主循环状态"""
    round: int = 0
    max_rounds: int = 3
    history: list[FeedbackSummary] = field(default_factory=list)
    status: str = "running"  # "running" | "success" | "failed" | "stopped"
    context_text: str = ""   # LLM 最后回复的文本内容