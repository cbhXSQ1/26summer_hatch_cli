"""Shell 命令执行工具"""

import subprocess
import os

from hatch.core.models import ToolResult
from hatch.tools.base import Tool


class ShellExecutor(Tool):
    name = "shell_executor"
    description = "执行 Shell 命令"
    parameters_schema = {
        "command": {"type": "string", "description": "要执行的命令"},
    }

    DEFAULT_TIMEOUT = 30

    def execute(self, params: dict) -> ToolResult:
        command = params["command"]
        timeout = params.get("timeout", self.DEFAULT_TIMEOUT)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            output = proc.stdout
            if proc.stderr:
                output += proc.stderr
            return ToolResult(
                success=proc.returncode == 0,
                output=output.strip() or "(no output)",
                error=proc.stderr.strip() if proc.stderr else None,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"命令超时 ({timeout}s)",
            )