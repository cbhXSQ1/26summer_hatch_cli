"""代码风格检查工具"""

import os
import subprocess
import sys

from hatch.core.models import ToolResult
from hatch.tools.base import Tool


class Linter(Tool):
    name = "linter"
    description = "运行 flake8 代码风格检查"
    parameters_schema = {
        "path": {"type": "string", "description": "目标文件路径"},
    }

    @staticmethod
    def _flake8_cmd() -> str:
        venv_flake8 = os.path.join(os.path.dirname(sys.executable), "flake8")
        if os.path.exists(venv_flake8) or os.path.exists(venv_flake8 + ".exe"):
            return venv_flake8
        return "flake8"

    def execute(self, params: dict) -> ToolResult:
        path = params["path"]
        try:
            proc = subprocess.run(
                [self._flake8_cmd(), path],
                capture_output=True,
                text=True,
                timeout=30,
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
                error="flake8 未安装，请运行: pip install flake8",
            )