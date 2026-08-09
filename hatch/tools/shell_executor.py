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
        "working_dir": {
            "type": "string",
            "description": "命令执行的工作目录（可选，默认当前工作目录）",
        },
    }

    DEFAULT_TIMEOUT = 30

    def execute(self, params: dict) -> ToolResult:
        command = params.get("command")
        if not command:
            return ToolResult(
                success=False,
                error="缺少 command 参数：请提供要执行的命令",
            )
        timeout = params.get("timeout", self.DEFAULT_TIMEOUT)
        cwd = params.get("working_dir") or os.getcwd()
        if not os.path.isdir(cwd):
            os.makedirs(cwd, exist_ok=True)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            # 某些命令/编码场景下 stdout/stderr 可能为 None，防御处理
            output = (proc.stdout or "") + (proc.stderr or "")
            return ToolResult(
                success=proc.returncode == 0,
                output=output.strip() or "(no output)",
                error=(proc.stderr or "").strip() or None,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"命令超时 ({timeout}s)",
            )