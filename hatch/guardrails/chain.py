"""护栏规则链"""

from hatch.core.models import Action, GuardrailResult
from hatch.guardrails.rules import GuardrailRule


class GuardrailChain:
    """串联多条护栏规则，取最高严重级别"""

    def __init__(self) -> None:
        self._rules: list[GuardrailRule] = []

    def add_rule(self, rule: GuardrailRule) -> None:
        self._rules.append(rule)

    def check(self, action: Action) -> GuardrailResult:
        approval_needed = False
        approval_reason = ""
        for rule in self._rules:
            result = rule.check(action)
            if not result.allowed:
                if rule.severity == "block":
                    return result
                if rule.severity == "approve":
                    approval_needed = True
                    approval_reason = result.reason
        if approval_needed:
            return GuardrailResult(
                allowed=False,
                reason=approval_reason,
                requires_approval=True,
            )
        return GuardrailResult(allowed=True)