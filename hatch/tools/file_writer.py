"""文件写入工具"""

import shutil
from datetime import datetime
from pathlib import Path

from hatch.core.models import ToolResult
from hatch.tools.base import Tool


SYSTEM_ROOTS = {
    "/", "/etc", "/bin", "/boot", "/dev", "/lib", "/proc", "/root",
    "/sbin", "/sys", "/usr", "/var",
    "C:\\Windows", "C:\\Windows\\System32", "C:\\Program Files",
}


class FileWriter(Tool):
    name = "file_writer"
    description = "写入或修改文件内容"
    parameters_schema = {
        "path": {"type": "string", "description": "文件路径"},
        "content": {"type": "string", "description": "新内容"},
    }

    def execute(self, params: dict) -> ToolResult:
        path = Path(params["path"]).resolve()
        content = params["content"]

        for root in SYSTEM_ROOTS:
            root_path = Path(root)
            if root == "/":
                # 根目录不能作为前缀拦截：Linux 上所有绝对路径都是 / 的相对路径。
                # 只有目标就是根目录本身时才拒绝。
                if path == root_path:
                    return ToolResult(success=False, error=f"拒绝写入系统目录: {root}")
                continue
            try:
                path.relative_to(root_path)
                return ToolResult(success=False, error=f"拒绝写入系统目录: {root}")
            except ValueError:
                continue

        if path.exists():
            backup_dir = path.parent / ".hatch_backup"
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{path.name}.{timestamp}"
            shutil.copy2(path, backup_path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(success=True, output=f"写入成功: {path}")