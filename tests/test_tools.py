"""T2.1: Tool 基类 + ToolRegistry 测试"""

import subprocess
import pytest
from unittest.mock import patch, MagicMock

from hatch.core.models import Action, ToolResult
from hatch.tools.base import Tool
from hatch.tools.registry import ToolRegistry


class FakeEchoTool(Tool):
    name = "echo"
    description = "Returns the input as output"
    parameters_schema = {"message": {"type": "string"}}

    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=True, output=params.get("message", ""))


class FakeFailingTool(Tool):
    name = "failer"
    description = "Always fails"
    parameters_schema = {}

    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=False, error="intentional failure")


class TestToolABC:
    """Tool 抽象基类"""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            Tool()  # type: ignore[abstract]

    def test_subclass_without_execute(self) -> None:
        with pytest.raises(TypeError):
            class Incomplete(Tool):
                name = "bad"
                description = "missing execute"
                parameters_schema = {}
            Incomplete()  # type: ignore[abstract]


class TestToolRegistry:
    """ToolRegistry"""

    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        tool = FakeEchoTool()
        registry.register(tool)
        assert registry.get("echo") is tool

    def test_get_unknown_tool(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="unknown"):
            registry.get("unknown")

    def test_list_tools(self) -> None:
        registry = ToolRegistry()
        registry.register(FakeEchoTool())
        registry.register(FakeFailingTool())
        names = [t.name for t in registry.list_tools()]
        assert "echo" in names
        assert "failer" in names

    def test_dispatch_calls_correct_tool(self) -> None:
        registry = ToolRegistry()
        registry.register(FakeEchoTool())
        action = Action(tool_name="echo", parameters={"message": "hello"})
        result = registry.dispatch(action)
        assert result.success is True
        assert result.output == "hello"

    def test_dispatch_unknown_tool(self) -> None:
        registry = ToolRegistry()
        action = Action(tool_name="ghost", parameters={})
        result = registry.dispatch(action)
        assert result.success is False
        assert "ghost" in result.error or "unknown" in result.error.lower()

    def test_dispatch_passes_parameters(self) -> None:
        registry = ToolRegistry()
        registry.register(FakeEchoTool())
        action = Action(tool_name="echo", parameters={"message": "world"})
        result = registry.dispatch(action)
        assert result.output == "world"

    def test_dispatch_handles_tool_failure(self) -> None:
        registry = ToolRegistry()
        registry.register(FakeFailingTool())
        action = Action(tool_name="failer", parameters={})
        result = registry.dispatch(action)
        assert result.success is False
        assert result.error == "intentional failure"

    def test_dispatch_tool_raises_exception(self) -> None:
        registry = ToolRegistry()

        class ExplodingTool(Tool):
            name = "bomb"
            description = "goes boom"
            parameters_schema = {}

            def execute(self, params: dict) -> ToolResult:
                raise RuntimeError("BOOM")

        registry.register(ExplodingTool())
        action = Action(tool_name="bomb", parameters={})
        result = registry.dispatch(action)
        assert result.success is False
        assert "BOOM" in result.error


class TestFileReader:
    """FileReader"""

    def test_reads_text_file_with_line_numbers(self, tmp_path) -> None:
        from hatch.tools.file_reader import FileReader

        f = tmp_path / "test.txt"
        f.write_text("line one\nline two\n", encoding="utf-8")
        reader = FileReader()
        result = reader.execute({"path": str(f)})
        assert result.success is True
        assert "1: line one" in result.output
        assert "2: line two" in result.output

    def test_file_not_found(self, tmp_path) -> None:
        from hatch.tools.file_reader import FileReader

        reader = FileReader()
        result = reader.execute({"path": str(tmp_path / "no.txt")})
        assert result.success is False

    def test_file_exceeds_size_limit(self, tmp_path) -> None:
        from hatch.tools.file_reader import FileReader

        f = tmp_path / "large.txt"
        f.write_bytes(b"x" * 1_000_001)
        reader = FileReader()
        result = reader.execute({"path": str(f)})
        assert result.success is False
        assert "1MB" in result.error

    def test_binary_file(self, tmp_path) -> None:
        from hatch.tools.file_reader import FileReader

        f = tmp_path / "data.bin"
        f.write_bytes(b"\x80\x81\x82\xff\xfe")
        reader = FileReader()
        result = reader.execute({"path": str(f)})
        assert result.success is False
        assert "二进制" in result.error

    def test_reads_utf8_bom_file(self, tmp_path) -> None:
        """UTF-8 BOM 文件读取后不应残留 \\ufeff 字符。"""
        from hatch.tools.file_reader import FileReader

        f = tmp_path / "bom.txt"
        f.write_bytes(b"\xef\xbb\xbf# Hatch Config\nline2\n")
        reader = FileReader()
        result = reader.execute({"path": str(f)})
        assert result.success is True
        assert "\ufeff" not in result.output
        assert "1: # Hatch Config" in result.output

    def test_empty_file(self, tmp_path) -> None:
        from hatch.tools.file_reader import FileReader

        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        reader = FileReader()
        result = reader.execute({"path": str(f)})
        assert result.success is True
        assert result.output == ""


class TestFileWriter:
    """FileWriter"""

    def test_writes_content(self, tmp_path) -> None:
        from hatch.tools.file_writer import FileWriter

        f = tmp_path / "out.py"
        writer = FileWriter()
        result = writer.execute({"path": str(f), "content": "print('hi')"})
        assert result.success is True
        assert f.read_text(encoding="utf-8") == "print('hi')"

    def test_creates_backup(self, tmp_path) -> None:
        from hatch.tools.file_writer import FileWriter

        f = tmp_path / "original.txt"
        f.write_text("original", encoding="utf-8")
        writer = FileWriter()
        writer.execute({"path": str(f), "content": "modified"})
        backups = list(tmp_path.glob(".hatch_backup/original.txt*"))
        assert len(backups) >= 1

    def test_blocks_system_directory(self) -> None:
        from hatch.tools.file_writer import FileWriter

        writer = FileWriter()
        result = writer.execute({"path": "C:\\Windows\\test.txt", "content": "bad"})
        assert result.success is False
        assert "拒绝" in result.error or "系统" in result.error

    def test_creates_new_file_no_backup(self, tmp_path) -> None:
        from hatch.tools.file_writer import FileWriter

        f = tmp_path / "new_file.txt"
        writer = FileWriter()
        result = writer.execute({"path": str(f), "content": "fresh"})
        assert result.success is True
        backups = list(tmp_path.glob(".hatch_backup/*"))
        assert len(backups) == 0

    def test_creates_parent_directories(self, tmp_path) -> None:
        from hatch.tools.file_writer import FileWriter

        f = tmp_path / "a" / "b" / "c" / "nested.txt"
        writer = FileWriter()
        result = writer.execute({"path": str(f), "content": "deep"})
        assert result.success is True
        assert f.read_text(encoding="utf-8") == "deep"


class TestShellExecutor:
    """ShellExecutor"""

    def test_executes_simple_command(self) -> None:
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        result = exe.execute({"command": "echo hello"})
        assert result.success is True
        assert "hello" in result.output

    def test_captures_stderr(self) -> None:
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        result = exe.execute({"command": "python -c \"import sys; sys.stderr.write('err')\""})
        assert "err" in result.output or "err" in (result.error or "")

    def test_nonzero_exit_code(self) -> None:
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        result = exe.execute({"command": "python -c \"exit(1)\""})
        assert result.success is False
        assert result.exit_code == 1

    def test_timeout(self) -> None:
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        result = exe.execute({"command": "python -c \"import time; time.sleep(10)\"", "timeout": 1})
        assert result.success is False
        assert "超时" in result.error or "timeout" in result.error.lower()

    def test_custom_timeout(self) -> None:
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok", stderr=""
            )
            exe.execute({"command": "echo hi", "timeout": 5})
            assert mock_run.call_args[1]["timeout"] == 5

    def test_working_dir_parameter_respected(self, tmp_path) -> None:
        """working_dir 参数必须生效 — 命令应在指定目录执行。"""
        import sys
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        cmd = f'"{sys.executable}" -c "import os; print(os.getcwd())"'
        result = exe.execute({"command": cmd, "working_dir": str(tmp_path)})
        assert result.success is True
        assert str(tmp_path) in result.output

    def test_working_dir_missing_falls_back_to_cwd(self) -> None:
        """未传 working_dir 时回退到进程当前目录。"""
        import os
        import sys
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        cmd = f'"{sys.executable}" -c "import os; print(os.getcwd())"'
        result = exe.execute({"command": cmd})
        assert result.success is True
        assert os.getcwd() in result.output

    def test_none_output_does_not_crash(self) -> None:
        """stdout/stderr 为 None（部分命令/编码场景）时不崩溃。"""
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=None, stderr=None
            )
            result = exe.execute({"command": "weird"})
            assert result.success is True

    def test_decodes_utf8_output(self) -> None:
        """UTF-8 编码的输出（如 type 读取 UTF-8 文件）必须正确解码，不乱码。"""
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="\u4f60\u597d".encode("utf-8"), stderr=b""
            )
            result = exe.execute({"command": "type a.md"})
            assert result.success is True
            assert "\u4f60\u597d" in result.output

    def test_decodes_gbk_output(self) -> None:
        """GBK 编码的输出（cmd 中文统计行）也必须正确解码。"""
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="\u4e2a\u6587\u4ef6".encode("gbk"), stderr=b""
            )
            result = exe.execute({"command": "dir"})
            assert result.success is True
            assert "\u4e2a\u6587\u4ef6" in result.output

    def test_crlf_normalized_to_lf(self) -> None:
        """CRLF 行尾必须规范化为 LF — 否则 \\r 泄漏进上下文/回复（^M 乱码）。"""
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="line1\r\nline2\r\n".encode("utf-8"),
                stderr=b"",
            )
            result = exe.execute({"command": "dir"})
            assert result.success is True
            assert "\r" not in result.output
            assert "line1\nline2" in result.output

    def test_missing_command_key_returns_graceful_error(self) -> None:
        """parameters 缺少 command 时返回明确错误，而不是抛 KeyError。"""
        from hatch.tools.shell_executor import ShellExecutor

        exe = ShellExecutor()
        result = exe.execute({})
        assert result.success is False
        assert "command" in (result.error or "")


class TestTestRunner:
    """TestRunner"""

    def test_runs_pytest_on_file(self, tmp_path) -> None:
        from hatch.tools.test_runner import TestRunner

        test_file = tmp_path / "test_sample.py"
        test_file.write_text("def test_pass():\n    assert True\n", encoding="utf-8")
        runner = TestRunner()
        result = runner.execute({"path": str(tmp_path)})
        assert result.success is True
        assert "passed" in result.output

    def test_detects_failing_test(self, tmp_path) -> None:
        from hatch.tools.test_runner import TestRunner

        test_file = tmp_path / "test_fail.py"
        test_file.write_text("def test_fail():\n    assert False\n", encoding="utf-8")
        runner = TestRunner()
        result = runner.execute({"path": str(tmp_path)})
        assert result.success is False
        assert "failed" in result.output

    def test_timeout(self, tmp_path) -> None:
        from hatch.tools.test_runner import TestRunner

        test_file = tmp_path / "test_slow.py"
        test_file.write_text(
            "import time\n"
            "def test_slow():\n"
            "    time.sleep(10)\n"
            "    assert True\n",
            encoding="utf-8",
        )
        runner = TestRunner()
        result = runner.execute({"path": str(tmp_path), "timeout": 1})
        assert result.success is False
        assert "超时" in result.error or "timeout" in result.error.lower()

    def test_pytest_not_installed(self) -> None:
        from hatch.tools.test_runner import TestRunner

        runner = TestRunner()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = runner.execute({"path": "."})
        assert result.success is False
        assert "pytest" in result.error.lower() and "未安装" in result.error


class TestLinter:
    """Linter"""

    def test_runs_flake8(self, tmp_path) -> None:
        from hatch.tools.linter import Linter

        py_file = tmp_path / "sample.py"
        py_file.write_text("x = 1\n\n\n", encoding="utf-8")
        linter = Linter()
        result = linter.execute({"path": str(tmp_path)})
        assert isinstance(result.output, str)
        assert result.exit_code is not None

    def test_flake8_not_installed(self) -> None:
        from hatch.tools.linter import Linter

        linter = Linter()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = linter.execute({"path": "."})
        assert result.success is False
        assert "flake8" in result.error.lower() and "未安装" in result.error


class TestTypeChecker:
    """TypeChecker"""

    def test_runs_mypy(self, tmp_path) -> None:
        from hatch.tools.type_checker import TypeChecker

        py_file = tmp_path / "sample.py"
        py_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
        checker = TypeChecker()
        result = checker.execute({"path": str(tmp_path)})
        assert isinstance(result.output, str)
        assert result.exit_code is not None

    def test_mypy_not_installed(self) -> None:
        from hatch.tools.type_checker import TypeChecker

        checker = TypeChecker()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = checker.execute({"path": "."})
        assert result.success is False
        assert "mypy" in result.error.lower() and "未安装" in result.error