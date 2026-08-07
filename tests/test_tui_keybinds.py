"""TUI keybinds 测试：下拉打开时 Tab 焦点切换被禁用"""

from prompt_toolkit.keys import Keys

from hatch.tui.keybinds import build_keybindings


class TestKeybinds:
    def _build(self, dropdown_open):
        state = {"open": dropdown_open}
        kb = build_keybindings(
            get_focus=lambda: "input",
            set_focus=lambda s: state.update(focus=s),
            activate_focus=lambda: None,
            on_arrow=lambda d: None,
            cancel_dropdown=lambda: None,
            is_dropdown_open=lambda: state["open"],
            submit_task=lambda t: None,
        )
        return kb, state

    def _find_binding(self, kb, key):
        for b in kb.bindings:
            for seq in b.keys:
                if key in seq:
                    return b
        return None

    def test_tab_allowed_when_dropdown_closed(self):
        kb, _ = self._build(dropdown_open=False)
        tab = self._find_binding(kb, Keys.Tab)
        assert tab is not None
        assert tab.filter() is True

    def test_tab_disabled_when_dropdown_open(self):
        kb, _ = self._build(dropdown_open=True)
        tab = self._find_binding(kb, Keys.Tab)
        assert tab is not None
        assert tab.filter() is False

    def test_s_tab_disabled_when_dropdown_open(self):
        kb, _ = self._build(dropdown_open=True)
        s_tab = self._find_binding(kb, Keys.BackTab)
        assert s_tab is not None
        assert s_tab.filter() is False

    def test_mouse_wheel_bindings_scroll(self):
        """scroll-up / scroll-down 绑定存在并调用 scroll_log。"""
        calls = []
        state = {"open": False}
        kb = build_keybindings(
            get_focus=lambda: "cwd",
            set_focus=lambda s: None,
            activate_focus=lambda: None,
            on_arrow=lambda d: None,
            cancel_dropdown=lambda: None,
            is_dropdown_open=lambda: state["open"],
            submit_task=lambda t: None,
            scroll_log=lambda delta: calls.append(delta),
        )
        up = self._find_binding(kb, Keys.ScrollUp)
        down = self._find_binding(kb, Keys.ScrollDown)
        assert up is not None
        assert down is not None

        # 直接调用 handler（传入假 event）
        fake = object()
        up.handler(fake)
        down.handler(fake)
        assert calls == [-3, 3]

    def test_no_scroll_bindings_without_scroll_log(self):
        """未提供 scroll_log 时不注册滚动绑定。"""
        kb, _ = self._build(dropdown_open=False)
        assert self._find_binding(kb, Keys.ScrollUp) is None
        assert self._find_binding(kb, Keys.ScrollDown) is None
