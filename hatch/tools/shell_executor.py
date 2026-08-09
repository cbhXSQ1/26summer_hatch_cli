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

    @staticmethod
    def _decode(data: bytes | str | None) -> str:
        """命令输出解码：优先 UTF-8，失败回退 GBK（Windows cmd 中文），
        再失败用 latin-1 兜底 —— 避免乱码注入上下文。
        同时把 CRLF 规范化为 LF（Windows 命令输出行尾），
        否则 \\r 会泄漏进上下文/回复（终端显示为 ^M）。"""
        if not data:
            return ""
        if isinstance(data, str):
            return data.replace("\r\n", "\n").replace("\r", "\n")
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return data.decode(enc).replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

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
                text=False,
                timeout=timeout,
                cwd=cwd,
            )
            stdout = self._decode(proc.stdout)
            stderr = self._decode(proc.stderr)
            output = stdout + stderr
            return ToolResult(
                success=proc.returncode == 0,
                output=output.strip() or "(no output)",
                error=stderr.strip() or None,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"命令超时 ({timeout}s)",
            )