"""Build prompt_toolkit Layout for Hatch TUI."""

from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.containers import Float, FloatContainer
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from hatch.tui.widgets import FocusableText, ConversationLog, DropdownMenu


def build_layout(
    conversation_log: ConversationLog,
    cwd_text: FocusableText,
    session_text: FocusableText,
    more_text: FocusableText,
    model_text: FocusableText,
    key_text: FocusableText,
    input_buffer: Buffer,
    model_dropdown: DropdownMenu | None = None,
    sessions_dropdown: DropdownMenu | None = None,
    focus_target: Window | None = None,
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

    floats = []
    for dd in (model_dropdown, sessions_dropdown):
        if dd is not None:
            floats.append(Float(content=dd.__pt_container__(), top=0, left=0))
    if floats:
        root = FloatContainer(root, floats=floats)

    if focus_target is not None:
        # 不可见焦点目标：height=0 不占空间，但属于布局树可聚焦
        root = HSplit([root, focus_target])

    layout = Layout(root, focused_element=input_window)
    layout.input_window = input_window
    return layout


def _build_toolbar(cwd, session, more, model, key) -> FormattedText:
    parts = []
    for ft in [cwd, session, more, model, key]:
        parts.extend(ft._get_formatted_text())
        parts.append(("", " | "))
    return FormattedText(parts[:-1])
