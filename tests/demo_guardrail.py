# -*- coding: utf-8 -*-
"""机制演示 1：护栏拦截危险动作"""

import sys
from hatch.core.llm import MockLLM
from hatch.core.loop import AgentLoop
from hatch.tools.registry import ToolRegistry
from hatch.guardrails.chain import GuardrailChain
from hatch.guardrails.rules import DangerousCommandRule
from hatch.config.loader import Config


def main() -> None:
    print("=" * 60)
    print("Demo 1: Guardrail intercepts dangerous action")
    print("=" * 60)

    llm = MockLLM([
        """```json
[{"tool_name": "shell_executor", "parameters": {"command": "rm -rf /"}}]
```""",
    ])

    registry = ToolRegistry()
    chain = GuardrailChain()
    chain.add_rule(DangerousCommandRule())

    print("\n[LLM] wants to execute: rm -rf /")
    print("[Guardrail] checking...")

    state = AgentLoop().run(
        task="clean up",
        llm=llm,
        registry=registry,
        guardrail_chain=chain,
        config=Config(),
    )

    assert state.status == "stopped", f"Expected 'stopped', got '{state.status}'"
    print("[Guardrail] DANGER BLOCKED")
    print("\nDemo 1 PASSED")


if __name__ == "__main__":
    main()