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
) -> KeyBindings:
    kb = KeyBindings()

    @kb.add("tab")
    def _(event):
        order = ["cwd", "session", "more", "model", "key", "input"]
        current = get_focus()
        idx = order.index(current) if current in order else -1
        next_idx = (idx + 1) % len(order)
        set_focus(order[next_idx])

    @kb.add("s-tab")
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

    @kb.add("up", filter=Condition(is_dropdown_open))
    def _(event):
        on_arrow(-1)

    @kb.add("down", filter=Condition(is_dropdown_open))
    def _(event):
        on_arrow(1)

    return kb
