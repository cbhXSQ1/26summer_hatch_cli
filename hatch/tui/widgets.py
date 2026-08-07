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
            return FormattedText([("reverse", f" {display} ")])
        return FormattedText([("", f" {display} ")])

    def __pt_container__(self) -> Window:
        return Window(
            content=FormattedTextControl(self._get_formatted_text),
            dont_extend_width=True,
            dont_extend_height=True,
        )


from prompt_toolkit.formatted_text import to_formatted_text
from hatch.tui.events import (
    StreamChunk, ToolCall, ToolResult, Feedback,
    RoundStart, RoundEnd, Done, Warning
)


class ConversationLog:
    """Scrollable conversation history area."""

    def __init__(self, max_lines: int = 500) -> None:
        self._lines: list[str] = []
        self.max_lines = max_lines

    def append_event(self, event) -> None:
        t = getattr(event, "type", None)
        if t == "stream_chunk":
            self._append_stream(getattr(event, "text", ""))
        else:
            text = self._format(event)
            if text:
                for line in text.split("\n"):
                    self._lines.append(line)
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]

    def _append_stream(self, text: str) -> None:
        """追加流式文本到当前行，遇到换行才断行。"""
        if not text:
            return
        parts = text.split("\n")
        if self._lines:
            self._lines[-1] += parts[0]
        else:
            self._lines.append(parts[0])
        for p in parts[1:]:
            self._lines.append(p)

    def _format(self, event) -> str:
        t = event.type
        if t == "stream_chunk":
            return event.text
        elif t == "round_start":
            return f"\n  Round {event.round}/{event.max_rounds}"
        elif t == "tool_call":
            return f"  >> {event.name}({_short_params(event.params)})"
        elif t == "tool_result":
            status = "OK" if event.success else "FAIL"
            detail = event.output[:80].replace("\n", " ") if event.output else ""
            return f"  << {event.name} [{status}] {detail}"
        elif t == "feedback":
            if event.success:
                return "  All checks passed"
            else:
                return f"  Feedback: {event.issues} issue(s)"
        elif t == "round_end":
            return "  ---" if not event.all_ok else ""
        elif t == "done":
            status = event.status
            rounds = event.rounds
            if status == "success":
                return f"\n  Task complete ({rounds} round)"
            elif status == "failed":
                return f"\n  Task failed ({rounds} round)"
            else:
                return f"\n  Stopped ({rounds} round)"
        elif t == "warning":
            return f"  Warning: {event.msg}"
        return ""

    def get_text(self) -> str:
        return "\n".join(self._lines)

    def __pt_container__(self):
        def _text():
            return to_formatted_text(self.get_text()) + [("[SetCursorPosition]", "")]

        return Window(
            content=FormattedTextControl(text=_text),
            wrap_lines=True,
            always_hide_cursor=True,
        )


def _short_params(params: dict) -> str:
    parts = []
    for k, v in list(params.items())[:2]:
        s = str(v)[:40]
        parts.append(f"{k}={s}")
    return ", ".join(parts)


class DropdownMenu:
    """Float dropdown list for More/Model selection. Keyboard-navigable."""

    def __init__(self, items: list[tuple[str, str]], title: str = "") -> None:
        """
        items: list of (display_label, value)
        """
        self.items = items
        self.title = title
        self.selected_index = 0
        self.visible = False

    def show(self) -> None:
        self.visible = True
        self.selected_index = 0

    def hide(self) -> None:
        self.visible = False

    def move_up(self) -> None:
        if not self.items:
            return
        self.selected_index = (self.selected_index - 1) % len(self.items)

    def move_down(self) -> None:
        if not self.items:
            return
        self.selected_index = (self.selected_index + 1) % len(self.items)

    def get_selected(self) -> tuple[str, str]:
        return self.items[self.selected_index]

    def _get_formatted_lines(self) -> list:
        lines = []
        if self.title:
            lines.append(("bold", f"  {self.title}"))
        for i, (label, _) in enumerate(self.items):
            if i == self.selected_index:
                lines.append(("reverse", f"> {label}"))
            else:
                lines.append(("", f"  {label}"))
        return lines

    def __pt_container__(self):
        return Window(
            content=FormattedTextControl(
                text=lambda: self._get_formatted_lines() if self.visible else [],
            ),
            dont_extend_width=True,
            dont_extend_height=True,
        )
