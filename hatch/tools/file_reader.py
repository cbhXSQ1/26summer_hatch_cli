"""文件读取工具"""

from pathlib import Path

from hatch.core.models import ToolResult
from hatch.tools.base import Tool


class FileReader(Tool):
    name = "file_reader"
    description = "读取文件内容，返回带行号的文本"
    parameters_schema = {
        "path": {"type": "string", "description": "文件路径"},
    }

    MAX_SIZE = 1_000_000  # 1MB

    def execute(self, params: dict) -> ToolResult:
        path = Path(params["path"])
        if not path.exists():
            return ToolResult(success=False, error=f"文件不存在: {path}")
        if path.stat().st_size > self.MAX_SIZE:
            return ToolResult(success=False, error="文件超过 1MB 限制")
        try:
            # utf-8-sig：自动剥离 BOM（Windows 下很多 UTF-8 文件带 BOM）
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return ToolResult(success=False, error="无法读取二进制文件")
        lines = content.splitlines()
        numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        return ToolResult(success=True, output=numbered)