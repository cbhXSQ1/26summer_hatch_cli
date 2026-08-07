# hatch/tui/keybinds.py
"""Key bindings for Hatch TUI."""

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition


def build_keybindings(
    get_focus,
    set_focus,
    activate_focus,
    on_arrow,
    cancel_dropdown,
    is_dropdown_open,
    submit_task,
    scroll_log=None,
) -> KeyBindings:
    kb = KeyBindings()
    not_dropdown = Condition(lambda: not is_dropdown_open())

    @kb.add("tab", filter=not_dropdown)
    def _(event):
        order = ["cwd", "session", "more", "model", "key", "input"]
        current = get_focus()
        idx = order.index(current) if current in order else -1
        next_idx = (idx + 1) % len(order)
        set_focus(order[next_idx])

    @kb.add("s-tab", filter=not_dropdown)
    def _(event):
        order = ["cwd", "session", "more", "model", "key", "input"]
        current = get_focus()
        idx = order.index(current) if current in order else -1
        next_idx = (idx - 1) % len(order)
        set_focus(order[next_idx])

    @kb.add("enter")
    def _(event):
        activate_focus()

    @kb.add("escape")
    def _(event):
        cancel_dropdown()

    @kb.add("c-e")
    def _(event):
        """打开系统编辑器输入（中文 IME 兜底）"""
        event.app.current_buffer.open_in_editor(event.app)

    @kb.add("up", filter=Condition(is_dropdown_open))
    def _(event):
        on_arrow(-1)

    @kb.add("down", filter=Condition(is_dropdown_open))
    def _(event):
        on_arrow(1)

    if scroll_log is not None:
        # 日志滚动：工具栏聚焦（非输入框、非下拉）时 ↑↓ 滚动，PgUp/PgDn 翻页
        toolbar_mode = Condition(
            lambda: not is_dropdown_open() and get_focus() != "input"
        )

        @kb.add("up", filter=toolbar_mode)
        def _(event):
            scroll_log(-1)

        @kb.add("down", filter=toolbar_mode)
        def _(event):
            scroll_log(1)

        @kb.add("pageup")
        def _(event):
            scroll_log(-20)

        @kb.add("pagedown")
        def _(event):
            scroll_log(20)

        # 鼠标滚轮滚动日志（需 mouse_support=True）
        @kb.add("<scroll-up>")
        def _(event):
            scroll_log(-3)

        @kb.add("<scroll-down>")
        def _(event):
            scroll_log(3)

    return kb
