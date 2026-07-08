"""T2.1: Tool 基类 + ToolRegistry 测试"""

import pytest
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