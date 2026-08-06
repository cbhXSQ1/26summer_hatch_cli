import pytest
from prompt_toolkit.formatted_text import FormattedText
from hatch.tui.widgets import FocusableText, ConversationLog, DropdownMenu


class TestFocusableText:
    def test_creates_with_default_text(self):
        ft = FocusableText("hello")
        assert ft.text == "hello"
        assert ft.is_focused is False

    def test_toggle_focus(self):
        ft = FocusableText("test")
        ft.set_focused(True)
        assert ft.is_focused is True
        ft.set_focused(False)
        assert ft.is_focused is False

    def test_format_different_when_focused(self):
        ft = FocusableText("item")
        ft.set_focused(False)
        unfocused = ft._get_formatted_text()
        ft.set_focused(True)
        focused = ft._get_formatted_text()
        assert unfocused != focused

    def test_container_is_window(self):
        from prompt_toolkit.layout import Window
        ft = FocusableText("x")
        container = ft.__pt_container__()
        assert isinstance(container, Window)


class TestConversationLog:
    def test_appends_stream_chunk(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=100)
        log.append_event(StreamChunk(text="hello"))
        assert "hello" in log.get_text()

    def test_appends_tool_call(self):
        from hatch.tui.events import ToolCall
        log = ConversationLog(max_lines=100)
        log.append_event(ToolCall(name="file_writer", params={"path": "x.py"}))
        text = log.get_text()
        assert "file_writer" in text

    def test_appends_tool_result_success(self):
        from hatch.tui.events import ToolResult
        log = ConversationLog(max_lines=100)
        log.append_event(ToolResult(name="test_runner", success=True, output="3 passed"))
        text = log.get_text()
        assert "test_runner" in text

    def test_autofollow_cursor_fragment(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=10)
        log.append_event(StreamChunk(text="hello"))
        fragments = log.__pt_container__().content.text()
        assert fragments[-1] == ("[SetCursorPosition]", "")


class TestDropdownMenu:
    def test_creates_with_items(self):
        menu = DropdownMenu(items=[("deepseek-v4-pro", "deepseek"), ("glm-5.2", "glm")])
        assert len(menu.items) == 2
        assert menu.selected_index == 0

    def test_move_selection(self):
        menu = DropdownMenu(items=[("a", "a"), ("b", "b"), ("c", "c")])
        menu.move_down()
        assert menu.selected_index == 1
        menu.move_up()
        assert menu.selected_index == 0

    def test_wraps_selection(self):
        menu = DropdownMenu(items=[("a", "a"), ("b", "b")])
        menu.move_down()
        menu.move_down()
        assert menu.selected_index == 0
        menu.move_up()
        assert menu.selected_index == 1

    def test_get_selected(self):
        menu = DropdownMenu(items=[("deepseek", "ds"), ("glm", "glm")])
        menu.move_down()
        label, value = menu.get_selected()
        assert label == "glm"
        assert value == "glm"

    def test_empty_menu_move_no_crash(self):
        menu = DropdownMenu(items=[])
        menu.move_up()
        menu.move_down()
        assert menu.selected_index == 0
