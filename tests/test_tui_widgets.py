import pytest
from unittest.mock import MagicMock
from prompt_toolkit.formatted_text import FormattedText
from hatch.tui.widgets import FocusableText, ConversationLog, DropdownMenu, LogControl


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

    def test_stream_chunks_accumulate_on_same_line(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=100)
        for ch in ["\u4f60", "\u597d", "\uff0c"]:  # 你，好，
            log.append_event(StreamChunk(text=ch))
        assert log.get_text() == "\u4f60\u597d\uff0c"
        assert len(log._lines) == 1

    def test_stream_chunk_with_embedded_newline_splits(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=100)
        log.append_event(StreamChunk(text="line1\nline2"))
        assert log.get_text() == "line1\nline2"
        assert len(log._lines) == 2
        log.append_event(StreamChunk(text=" more"))
        assert log.get_text() == "line1\nline2 more"
        assert len(log._lines) == 2

    def test_stream_filters_json_block(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=100)
        log.append_event(StreamChunk(text="\u597d\u7684\uff0c\u968f\u4fbf\u804a\u804a\u3002\n"))
        log.append_event(StreamChunk(text="```json\n[]\n```"))
        log.append_event(StreamChunk(text="\u5b8c\u6210"))
        text = log.get_text()
        assert "```json" not in text
        assert "[]" not in text
        assert "\u597d\u7684" in text
        assert "\u5b8c\u6210" in text

    def test_stream_filters_json_block_split_across_chunks(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=100)
        log.append_event(StreamChunk(text="text before\n```json"))
        log.append_event(StreamChunk(text="\n[]\n```"))
        log.append_event(StreamChunk(text="\nafter"))
        text = log.get_text()
        assert "```json" not in text
        assert "[]" not in text
        assert "text before" in text
        assert "after" in text


class TestConversationLogScroll:
    def _fill(self, n=10):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=100)
        log.append_event(StreamChunk(
            text="\n".join(f"line {i}" for i in range(n))
        ))
        return log

    def test_follows_tail_by_default(self):
        log = self._fill()
        assert log.at_tail() is True
        # 光标（SetCursorPosition）位于最后一行
        fragments = log.__pt_container__().content.text()
        styles = [f[0] for f in fragments]
        assert "[SetCursorPosition]" in styles
        assert styles.count("[SetCursorPosition]") == 1

    def test_scroll_up_moves_cursor(self):
        log = self._fill(10)
        log.scroll_up(1)
        assert log.at_tail() is False
        assert log._cursor_line == 8
        log.scroll_up(3)
        assert log._cursor_line == 5

    def test_scroll_down_returns_to_tail(self):
        log = self._fill(10)
        log.scroll_up(3)
        assert log._cursor_line == 6
        log.scroll_down(2)
        assert log._cursor_line == 8
        log.scroll_down(1)
        assert log.at_tail() is True  # 到底恢复跟随

    def test_scroll_up_clamped_at_top(self):
        log = self._fill(10)
        log.scroll_up(100)
        assert log._cursor_line == 0

    def test_follow_tail_resets(self):
        log = self._fill(10)
        log.scroll_up(2)
        log.follow_tail()
        assert log.at_tail() is True

    def test_unlimited_keeps_all_lines(self):
        """默认不限制行数：超过 500 行也不截断，全部可滚动浏览。"""
        from hatch.tui.events import StreamChunk
        log = ConversationLog()  # max_lines=None
        for i in range(600):
            log.append_event(StreamChunk(text=f"line {i}\n"))
        assert len(log._lines) >= 600  # 首行 + 每 chunk 一行（含尾部空行）
        assert "line 0" in log.get_text()
        assert "line 599" in log.get_text()

    def test_explicit_max_lines_still_trims(self):
        from hatch.tui.events import StreamChunk
        log = ConversationLog(max_lines=50)
        for i in range(100):
            log.append_event(StreamChunk(text=f"line {i}\n"))
        assert len(log._lines) <= 50

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
        styles = [f[0] for f in fragments]
        # 跟随模式：光标锚定在最后一行开头
        assert "[SetCursorPosition]" in styles
        cursor_idx = styles.index("[SetCursorPosition]")
        # 单行内容时光标在行首
        assert fragments[cursor_idx + 1][1] == "hello"

    def test_control_intercepts_wheel_anywhere(self):
        """控制层拦截滚轮：任意位置（含空白行/行尾）都滚动。"""
        from prompt_toolkit.mouse_events import (
            MouseEvent, MouseEventType, MouseButton,
        )
        from prompt_toolkit.mouse_events import Point

        log = self._fill(10)
        control = log.__pt_container__().content
        assert isinstance(control, LogControl)

        # 行尾空白位置（x 很大）也要能滚动
        ev = MouseEvent(
            position=Point(x=100, y=9), event_type=MouseEventType.SCROLL_UP,
            button=MouseButton.NONE, modifiers=frozenset(),
        )
        result = control.mouse_handler(ev)
        assert result is None
        assert log.at_tail() is False

    def test_mouse_handler_scrolls(self):
        """滚轮事件调用 scroll_up/scroll_down。"""
        from prompt_toolkit.mouse_events import (
            MouseEvent, MouseEventType, MouseButton, MouseModifier,
        )
        from prompt_toolkit.mouse_events import Point

        log = self._fill(10)

        ev_up = MouseEvent(
            position=Point(x=1, y=1), event_type=MouseEventType.SCROLL_UP,
            button=MouseButton.NONE, modifiers=frozenset(),
        )
        result = log._mouse_handler(ev_up)
        assert result is None
        assert log.at_tail() is False

        ev_down = MouseEvent(
            position=Point(x=1, y=1), event_type=MouseEventType.SCROLL_DOWN,
            button=MouseButton.NONE, modifiers=frozenset(),
        )
        log._mouse_handler(ev_down)
        assert log.at_tail() is True

    def test_mouse_handler_ignores_clicks(self):
        from prompt_toolkit.mouse_events import (
            MouseEvent, MouseEventType, MouseButton, MouseModifier,
        )
        from prompt_toolkit.mouse_events import Point
        log = self._fill(10)
        ev_click = MouseEvent(
            position=Point(x=1, y=1), event_type=MouseEventType.MOUSE_UP,
            button=MouseButton.LEFT, modifiers=frozenset(),
        )
        assert log._mouse_handler(ev_click) is NotImplemented


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
