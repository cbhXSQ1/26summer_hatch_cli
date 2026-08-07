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

    def test_escape_binding_is_eager(self):
        """Esc 必须 eager：抢占输入框 emacs 默认的 pass 绑定。"""
        kb, _ = self._build(dropdown_open=False)
        escs = [b for b in kb.bindings if Keys.Escape in b.keys[0]]
        assert escs
        assert all(b.eager() for b in escs)

    def test_toolbar_arrow_scrolls_3_lines(self):
        """工具栏聚焦时 ↑↓ 滚动 3 行（不灵敏修复）。"""
        calls = []
        state = {"open": False, "focus": "cwd"}
        kb = build_keybindings(
            get_focus=lambda: state["focus"],
            set_focus=lambda s: state.update(focus=s),
            activate_focus=lambda: None,
            on_arrow=lambda d: None,
            cancel_dropdown=lambda: None,
            is_dropdown_open=lambda: state["open"],
            submit_task=lambda t: None,
            scroll_log=lambda delta: calls.append(delta),
        )
        ups = [b for b in kb.bindings if Keys.Up in b.keys[0]]
        downs = [b for b in kb.bindings if Keys.Down in b.keys[0]]
        # 工具栏模式的 ↑（非下拉打开且非输入框聚焦）
        toolbar_up = next(b for b in ups if b.filter())
        toolbar_down = next(b for b in downs if b.filter())
        assert toolbar_up is not None
        toolbar_up.handler(object())
        toolbar_down.handler(object())
        assert calls == [-3, 3]
