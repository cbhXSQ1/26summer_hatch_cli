"""测试运行工具"""

import os
import subprocess
import sys

from hatch.core.models import ToolResult
from hatch.tools.base import Tool


class TestRunner(Tool):
    name = "test_runner"
    description = "运行 pytest 测试"
    parameters_schema = {
        "path": {"type": "string", "description": "测试目标路径"},
    }

    DEFAULT_TIMEOUT = 120

    @staticmethod
    def _pytest_cmd() -> str:
        """返回 pytest 可执行路径，优先使用当前 venv 中的 pytest"""
        venv_pytest = os.path.join(os.path.dirname(sys.executable), "pytest")
        if os.path.exists(venv_pytest) or os.path.exists(venv_pytest + ".exe"):
            return venv_pytest
        return "pytest"

    def execute(self, params: dict) -> ToolResult:
        path = params["path"]
        timeout = params.get("timeout", self.DEFAULT_TIMEOUT)
        try:
            proc = subprocess.run(
                [self._pytest_cmd(), path, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            output = proc.stdout + proc.stderr
            return ToolResult(
                success=proc.returncode == 0,
                output=output.strip() or "(no output)",
                exit_code=proc.returncode,
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="pytest 未安装，请运行: pip install pytest",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"测试超时 ({timeout}s)",
            )