# -*- coding: utf-8 -*-
"""机制演示 2：反馈闭环修正"""

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
    print("Demo 2: Feedback loop drives correction")
    print("=" * 60)

    orig_dir = os.getcwd()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        os.chdir(tmp)

        llm = MockLLM([
            # Round 1: write buggy code + run test
            """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_demo.py", "content": "def test_fail():\\n    assert 1 == 2"}},
{"tool_name": "test_runner", "parameters": {"path": "test_demo.py"}}]
```""",
            # Round 2: fix code based on feedback + run test
            """```json
[{"tool_name": "file_writer", "parameters": {"path": "test_demo.py", "content": "def test_pass():\\n    assert 1 == 1"}},
{"tool_name": "test_runner", "parameters": {"path": "test_demo.py"}}]
```""",
        ])

        registry = ToolRegistry()
        registry.register(FileWriter())
        registry.register(TestRunner())
        feedback_engine = FeedbackEngine()

        print("\n[Round 1] LLM writes buggy code and runs test...")
        state = AgentLoop().run(
            task="fix test",
            llm=llm,
            registry=registry,
            feedback_engine=feedback_engine,
            config=Config(),
        )

        assert len(state.history) >= 2, f"Should have >=2 feedback, got {len(state.history)}"
        test_fb = state.history[1]  # test_runner feedback
        print(f"  Round 1 test feedback: success={test_fb.success}, issues={test_fb.total_issues}")
        assert test_fb.success is False, "Round 1 test should fail"

        print(f"  Final status: {state.status}, rounds: {state.round}")
        print("\nDemo 2 PASSED")

    os.chdir(orig_dir)


if __name__ == "__main__":
    main()