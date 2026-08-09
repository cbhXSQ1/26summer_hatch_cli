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

    def test_parses_xml_tool_calls(self) -> None:
        """Anthropic 风格 <tool_calls>/<invoke> 必须被解析为动作。"""
        output = """<tool_calls>
<invoke name="shell_executor">
<parameter name="command">dir</parameter>
<parameter name="working_dir">E:\\summerschool</parameter>
</invoke>
</tool_calls>"""
        actions, status = ActionParser.parse_status(output)
        assert status == "ok"
        assert len(actions) == 1
        assert actions[0].tool_name == "shell_executor"
        assert actions[0].parameters == {"command": "dir", "working_dir": "E:\\summerschool"}

    def test_xml_mixed_with_text(self) -> None:
        """文本 + XML 工具调用 → 应解析出动作而不是判为纯文本。"""
        output = (
            "\u597d\u7684\uff0c\u6211\u9a6c\u4e0a\u6267\u884c\u3002\n"
            "<tool_calls>\n"
            '<invoke name="shell_executor">\n'
            "<parameter name=\"command\">dir</parameter>\n"
            "</invoke>\n"
            "</tool_calls>"
        )
        actions, status = ActionParser.parse_status(output)
        assert status == "ok"
        assert len(actions) == 1
        assert actions[0].tool_name == "shell_executor"

    def test_multiple_xml_invokes(self) -> None:
        output = """<tool_calls>
<invoke name="file_reader"><parameter name="path">a.py</parameter></invoke>
<invoke name="shell_executor"><parameter name="command">pytest</parameter></invoke>
</tool_calls>"""
        actions, status = ActionParser.parse_status(output)
        assert status == "ok"
        assert len(actions) == 2
        assert [a.tool_name for a in actions] == ["file_reader", "shell_executor"]

    def test_malformed_xml_is_invalid_json(self) -> None:
        """存在 <invoke> 结构但解析失败 → 提醒重试而不是静默。"""
        output = "<tool_calls>\n<invoke name=\"shell_executor\">\n</tool_calls>"
        actions, status = ActionParser.parse_status(output)
        assert actions == []
        assert status == "invalid_json"

    def test_extract_text_strips_xml_block(self) -> None:
        output = (
            "\u597d\u7684\u3002\n"
            "<tool_calls>\n"
            '<invoke name="x"><parameter name="y">z</parameter></invoke>\n'
            "</tool_calls>"
        )
        text = ActionParser.extract_text(output)
        assert "\u597d\u7684" in text
        assert "<invoke" not in text
        assert "<tool_calls>" not in text

    def test_has_json_block_detects_xml(self) -> None:
        assert ActionParser.has_json_block(
            "<tool_calls><invoke name=\"x\"></invoke></tool_calls>"
        ) is True