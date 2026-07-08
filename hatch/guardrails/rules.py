"""护栏规则"""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from hatch.core.models import Action, GuardrailResult


class GuardrailRule(ABC):
    severity: str  # "block" | "approve"

    @abstractmethod
    def check(self, action: Action) -> GuardrailResult:
        ...


class DangerousCommandRule(GuardrailRule):
    severity = "block"

    PATTERNS = [
        r"rm\s+-rf\s+/",
        r"dd\s+if=",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
        r"mkfs\.",
        r">\s*/dev/sd",
    ]

    def check(self, action: Action) -> GuardrailResult:
        if action.tool_name != "shell_executor":
            return GuardrailResult(allowed=True)
        cmd = action.parameters.get("command", "")
        for pattern in self.PATTERNS:
            if re.search(pattern, cmd):
                return GuardrailResult(
                    allowed=False,
                    reason=f"危险命令被拦截: {cmd}",
                )
        return GuardrailResult(allowed=True)


class ApprovalCommandRule(GuardrailRule):
    severity = "approve"

    PATTERNS = [
        r"git\s+push\s+.*--force",
        r"pip\s+uninstall",
        r"chmod\s+777",
        r"rm\s+-rf\s+(?!.*/).*",  # rm -rf 非 / 路径
    ]

    def check(self, action: Action) -> GuardrailResult:
        if action.tool_name != "shell_executor":
            return GuardrailResult(allowed=True)
        cmd = action.parameters.get("command", "")
        for pattern in self.PATTERNS:
            if re.search(pattern, cmd):
                return GuardrailResult(
                    allowed=False,
                    reason=f"需要审批: {cmd}",
                    requires_approval=True,
                )
        return GuardrailResult(allowed=True)


class NetworkRequestRule(GuardrailRule):
    severity = "approve"

    PATTERNS = [r"\bcurl\b", r"\bwget\b"]

    def check(self, action: Action) -> GuardrailResult:
        if action.tool_name != "shell_executor":
            return GuardrailResult(allowed=True)
        cmd = action.parameters.get("command", "")
        for pattern in self.PATTERNS:
            if re.search(pattern, cmd):
                return GuardrailResult(
                    allowed=False,
                    reason=f"外部网络请求需审批: {cmd}",
                    requires_approval=True,
                )
        return GuardrailResult(allowed=True)


class PathTraversalRule(GuardrailRule):
    severity = "block"

    SYSTEM_ROOTS = [
        "/etc", "/bin", "/boot", "/dev", "/lib", "/proc", "/root",
        "/sbin", "/sys", "/usr", "/var",
        "C:\\Windows", "C:\\Windows\\System32",
    ]

    def check(self, action: Action) -> GuardrailResult:
        if action.tool_name not in ("file_reader", "file_writer"):
            return GuardrailResult(allowed=True)
        path = action.parameters.get("path", "")
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError):
            return GuardrailResult(allowed=True)
        for root in self.SYSTEM_ROOTS:
            try:
                resolved.relative_to(root)
                return GuardrailResult(
                    allowed=False,
                    reason=f"禁止访问系统目录: {path}",
                )
            except ValueError:
                pass
            if str(path).startswith(root):
                return GuardrailResult(
                    allowed=False,
                    reason=f"禁止访问系统目录: {path}",
                )
        return GuardrailResult(allowed=True)