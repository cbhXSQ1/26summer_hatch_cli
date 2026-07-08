"""HITL 人工审批交互"""

from hatch.core.models import Action


class HITLHandler:
    """人工审批处理器"""

    TIMEOUT = 60

    def __init__(self, input_func=None) -> None:
        self._input = input_func or input

    def request_approval(self, action: Action) -> bool:
        print(f"\n[HITL] 需要审批的操作:")
        print(f"  工具: {action.tool_name}")
        print(f"  参数: {action.parameters}")
        try:
            response = self._input("  是否允许? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return response == "y" or response == "yes"