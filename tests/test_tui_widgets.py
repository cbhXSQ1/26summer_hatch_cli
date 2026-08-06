import pytest
from prompt_toolkit.formatted_text import FormattedText
from hatch.tui.widgets import FocusableText


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
