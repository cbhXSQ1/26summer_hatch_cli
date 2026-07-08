"""T3.1: 护栏规则 测试"""

from hatch.core.models import Action, GuardrailResult
from hatch.guardrails.rules import (
    DangerousCommandRule,
    ApprovalCommandRule,
    NetworkRequestRule,
    PathTraversalRule,
)


class TestDangerousCommandRule:
    """危险命令规则"""

    def test_blocks_rm_rf_root(self) -> None:
        rule = DangerousCommandRule()
        action = Action(tool_name="shell_executor", parameters={"command": "rm -rf /"})
        result = rule.check(action)
        assert result.allowed is False
        assert "rm" in result.reason.lower()

    def test_blocks_dd(self) -> None:
        rule = DangerousCommandRule()
        action = Action(tool_name="shell_executor", parameters={"command": "dd if=/dev/zero of=/dev/sda"})
        result = rule.check(action)
        assert result.allowed is False

    def test_allows_normal_command(self) -> None:
        rule = DangerousCommandRule()
        action = Action(tool_name="shell_executor", parameters={"command": "ls -la"})
        result = rule.check(action)
        assert result.allowed is True

    def test_ignores_non_shell_actions(self) -> None:
        rule = DangerousCommandRule()
        action = Action(tool_name="file_reader", parameters={"path": "rm -rf /"})
        result = rule.check(action)
        assert result.allowed is True


class TestApprovalCommandRule:
    """需审批命令规则"""

    def test_requires_approval_for_git_push_force(self) -> None:
        rule = ApprovalCommandRule()
        action = Action(tool_name="shell_executor", parameters={"command": "git push --force"})
        result = rule.check(action)
        assert result.requires_approval is True
        assert result.allowed is False

    def test_requires_approval_for_pip_uninstall(self) -> None:
        rule = ApprovalCommandRule()
        action = Action(tool_name="shell_executor", parameters={"command": "pip uninstall requests"})
        result = rule.check(action)
        assert result.requires_approval is True

    def test_allows_normal_command(self) -> None:
        rule = ApprovalCommandRule()
        action = Action(tool_name="shell_executor", parameters={"command": "pip install requests"})
        result = rule.check(action)
        assert result.allowed is True


class TestNetworkRequestRule:
    """网络请求规则"""

    def test_requires_approval_for_curl(self) -> None:
        rule = NetworkRequestRule()
        action = Action(tool_name="shell_executor", parameters={"command": "curl https://example.com"})
        result = rule.check(action)
        assert result.requires_approval is True

    def test_requires_approval_for_wget(self) -> None:
        rule = NetworkRequestRule()
        action = Action(tool_name="shell_executor", parameters={"command": "wget https://example.com"})
        result = rule.check(action)
        assert result.requires_approval is True


class TestPathTraversalRule:
    """路径越界规则"""

    def test_blocks_etc_passwd(self) -> None:
        rule = PathTraversalRule()
        action = Action(tool_name="file_reader", parameters={"path": "/etc/passwd"})
        result = rule.check(action)
        assert result.allowed is False

    def test_blocks_windows_system32(self) -> None:
        rule = PathTraversalRule()
        action = Action(tool_name="file_reader", parameters={"path": "C:\\Windows\\System32\\config"})
        result = rule.check(action)
        assert result.allowed is False