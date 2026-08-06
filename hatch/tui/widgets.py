"""TUI widgets: FocusableText, DropdownMenu, ConversationLog."""

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl


class FocusableText:
    """A toolbar item that highlights when focused."""

    def __init__(self, text: str = "", prefix: str = "") -> None:
        self.text = text
        self.prefix = prefix
        self.is_focused = False

    def set_focused(self, focused: bool) -> None:
        self.is_focused = focused

    def update_text(self, text: str) -> None:
        self.text = text

    def _get_formatted_text(self) -> FormattedText:
        display = f"{self.prefix}{self.text}"
        if self.is_focused:
            return FormattedText([("bg:#ffffff fg:#000000", f" {display} ")])
        return FormattedText([("", f" {display} ")])

    def __pt_container__(self) -> Window:
        return Window(
            content=FormattedTextControl(self._get_formatted_text),
            dont_extend_width=True,
            dont_extend_height=True,
        )
