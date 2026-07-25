"""T4.1: ActionParser 测试"""

from hatch.core.parser import ActionParser


class TestActionParser:
    """ActionParser"""

    def test_parses_single_action(self) -> None:
        output = """```json
[{"tool_name": "file_reader", "parameters": {"path": "app.py"}}]
```"""
        actions = ActionParser.parse(output)
        assert len(actions) == 1
        assert actions[0].tool_name == "file_reader"
        assert actions[0].parameters == {"path": "app.py"}

    def test_parses_multiple_actions(self) -> None:
        output = """[
            {"tool_name": "file_reader", "parameters": {"path": "app.py"}},
            {"tool_name": "shell_executor", "parameters": {"command": "pytest"}}
        ]"""
        actions = ActionParser.parse(output)
        assert len(actions) == 2
        assert actions[0].tool_name == "file_reader"
        assert actions[1].tool_name == "shell_executor"

    def test_invalid_json_returns_empty(self) -> None:
        actions = ActionParser.parse("not json at all")
        assert actions == []

    def test_no_json_block_returns_empty(self) -> None:
        actions = ActionParser.parse("just some text without json")
        assert actions == []

    def test_missing_tool_name_skipped(self) -> None:
        output = """[
            {"parameters": {"path": "app.py"}},
            {"tool_name": "shell_executor", "parameters": {"command": "ls"}}
        ]"""
        actions = ActionParser.parse(output)
        assert len(actions) == 1
        assert actions[0].tool_name == "shell_executor"

    def test_stores_raw_llm_output(self) -> None:
        output = """[{"tool_name": "echo", "parameters": {}}]"""
        actions = ActionParser.parse(output)
        assert actions[0].raw_llm_output == output

    def test_extract_text_outside_json(self) -> None:
        output = """这是一段回复文本。
```json
[]
```"""
        text = ActionParser.extract_text(output)
        assert "这是一段回复文本" in text
        assert "[]" not in text

    def test_extract_text_no_code_block(self) -> None:
        output = "纯文本回复，没有代码块"
        text = ActionParser.extract_text(output)
        assert text == "纯文本回复，没有代码块"

    def test_extract_text_empty(self) -> None:
        output = """```json
[]
```"""
        text = ActionParser.extract_text(output)
        assert text == ""

    def test_has_json_block_with_fence(self) -> None:
        assert ActionParser.has_json_block("```json\n[]\n```") is True

    def test_has_json_block_bare_array(self) -> None:
        assert ActionParser.has_json_block("[{\"tool\": \"x\"}]") is True

    def test_has_json_block_no_json(self) -> None:
        assert ActionParser.has_json_block("just some text") is False