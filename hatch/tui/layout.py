"""Build prompt_toolkit Layout for Hatch TUI."""

from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from hatch.tui.widgets import FocusableText, ConversationLog


def build_layout(
    conversation_log: ConversationLog,
    cwd_text: FocusableText,
    session_text: FocusableText,
    more_text: FocusableText,
    model_text: FocusableText,
    key_text: FocusableText,
    input_buffer: Buffer,
) -> Layout:
    separator = Window(height=1, content=FormattedTextControl(
        FormattedText([("class:separator", "-" * 80)])
    ))
    input_window = Window(
        content=BufferControl(buffer=input_buffer),
        height=1, dont_extend_height=True,
    )
    toolbar = Window(
        content=FormattedTextControl(
            text=lambda: _build_toolbar(cwd_text, session_text, more_text, model_text, key_text),
        ),
        height=1, dont_extend_height=True,
    )
    root = HSplit([
        conversation_log.__pt_container__(),
        separator, input_window, separator, toolbar,
    ])
    return Layout(root, focused_element=input_window)


def _build_toolbar(cwd, session, more, model, key) -> FormattedText:
    parts = []
    for ft in [cwd, session, more, model, key]:
        parts.extend(ft._get_formatted_text())
        parts.append(("", " | "))
    return FormattedText(parts[:-1])
