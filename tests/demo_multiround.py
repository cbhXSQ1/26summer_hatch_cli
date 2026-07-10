# -*- coding: utf-8 -*-
"""机制演示 3：多轮反馈闭环（重点维度）"""

import sys, tempfile, os
from pathlib import Path
from hatch.core.llm import MockLLM
from hatch.core.loop import AgentLoop
from hatch.tools.registry import ToolRegistry
from hatch.tools.file_writer import FileWriter
from hatch.tools.test_runner import TestRunner
from hatch.feedback.engine import FeedbackEngine
from hatch.config.loader import Config


def main() -> None:
    print("=" * 60)
    print("Demo 3: Multi-round feedback loop (deep dimension)")
    print("=" * 60)

    orig_dir = os.getcwd()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        os.chdir(tmp)

        llm = MockLLM([
            # Round 1: syntax error
            """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_demo.py", "content": "def test_bad syntax error"}},
{"tool_name": "test_runner", "parameters": {"path": "test_demo.py"}}]
```""",
            # Round 2: logic error
            """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_demo.py", "content": "def test_fail():\\n    assert 1 == 2"}},
{"tool_name": "test_runner", "parameters": {"path": "test_demo.py"}}]
```""",
            # Round 3: all pass
            """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_demo.py", "content": "def test_pass():\\n    assert 1 == 1"}},
{"tool_name": "test_runner", "parameters": {"path": "test_demo.py"}}]
```""",
        ])

        registry = ToolRegistry()
        registry.register(FileWriter())
        registry.register(TestRunner())
        feedback_engine = FeedbackEngine()

        print("\n[Round 1] Syntax error...")
        state = AgentLoop().run(
            task="fix code",
            llm=llm,
            registry=registry,
            feedback_engine=feedback_engine,
            config=Config(),
        )

        print(f"  Total rounds: {state.round}/{state.max_rounds}")
        for i, h in enumerate(state.history):
            cats = {c.name: n for c, n in h.by_category.items()}
            print(f"  Feedback {i+1}: success={h.success}, issues={h.total_issues}, categories={cats}")

        print(f"\n  Final status: {state.status}")
        assert len(state.history) >= 3, f"Should have >=3 feedback, got {len(state.history)}"
        print("\nDemo 3 PASSED")

    os.chdir(orig_dir)


if __name__ == "__main__":
    main()