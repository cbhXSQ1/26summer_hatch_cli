"""类型检查工具"""

import os
import subprocess
import sys

from hatch.core.models import ToolResult
from hatch.tools.base import Tool


class TypeChecker(Tool):
    name = "type_checker"
    description = "运行 mypy 类型检查"
    parameters_schema = {
        "path": {"type": "string", "description": "目标文件路径"},
    }

    @staticmethod
    def _mypy_cmd() -> str:
        venv_mypy = os.path.join(os.path.dirname(sys.executable), "mypy")
        if os.path.exists(venv_mypy) or os.path.exists(venv_mypy + ".exe"):
            return venv_mypy
        return "mypy"

    def execute(self, params: dict) -> ToolResult:
        path = params["path"]
        try:
            proc = subprocess.run(
                [self._mypy_cmd(), path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.getcwd(),
            )
            output = proc.stdout + proc.stderr
            return ToolResult(
                success=proc.returncode == 0,
                output=output.strip() or "(no issues)",
                exit_code=proc.returncode,
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="mypy 未安装，请运行: pip install mypy",
            )