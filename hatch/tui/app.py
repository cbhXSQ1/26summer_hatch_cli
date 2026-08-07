# hatch/tui/app.py
"""Main Hatch TUI Application."""

import asyncio
import os
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.containers import Window

from hatch.core.llm import LLMBackend
from hatch.config.loader import Config
from hatch.memory.session_manager import SessionManager

from hatch.tui.layout import build_layout
from hatch.tui.widgets import FocusableText, ConversationLog, DropdownMenu
from hatch.tui.keybinds import build_keybindings
from hatch.tui.agent import run_agent_async
from hatch.tui.naming import auto_name


class HatchChatApp:
    """Main prompt_toolkit Application for Hatch interactive chat."""

    def __init__(
        self,
        workdir: str,
        llm: LLMBackend,
        config: Config,
        session_manager: SessionManager,
        session_id: str,
        session_name: str,
        is_new: bool = True,
        key_manager=None,
    ) -> None:
        self.workdir = workdir
        self.llm = llm
        self.config = config
        self.session_manager = session_manager
        self.session_id = session_id
        self.session_name = session_name
        self.is_new = is_new
        from hatch.security.key_manager import KeyManager
        self.km = key_manager or KeyManager()

        # Widgets
        self.conv_log = ConversationLog()
        self.cwd_text = FocusableText(workdir[-40:], prefix="")
        self.session_text = FocusableText(session_name[:15], prefix="")
        self.more_text = FocusableText("...", prefix="")
        self.model_text = FocusableText(
            f"{config.llm.provider}/{config.llm.model}", prefix=""
        )
        self.key_text = FocusableText("key", prefix="")

        # Dropdowns — 由配置驱动
        self.model_dropdown = DropdownMenu(
            items=self._build_model_items(),
            title="Select Model",
        )
        self.sessions_dropdown = DropdownMenu(items=[], title="Sessions")
        self.key_dropdown = DropdownMenu(items=[], title="Keys")

        # Focus state
        self._focus: str = "input"
        self._all_widgets = [self.cwd_text, self.session_text, self.more_text,
                              self.model_text, self.key_text]
        self._focus_map = {
            "cwd": 0, "session": 1, "more": 2, "model": 3, "key": 4,
        }

        # Agent state
        self._running_task: asyncio.Task | None = None
        self._is_first_reply = True
        self._first_task = ""
        self._first_reply_collected = ""
        # 待处理模式: None / "rename" / "key_name" / "key_base" / "key_models" / "key_key"
        self._pending_mode: str | None = None
        self._key_add_name = ""
        self._key_add_base = ""
        self._key_add_models: list[str] = []

        # Input buffer
        self.input_buffer = Buffer(multiline=False)

        # 不可见的焦点目标：进入工具栏模式时接管真实焦点，
        # 让键盘输入不再进入输入框（height=0 不占空间）
        self._focus_buffer = Buffer()
        self._focus_target = Window(
            content=BufferControl(buffer=self._focus_buffer),
            height=0,
        )

        # Event queue
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=128)

        # Build keybindings
        self._kb = build_keybindings(
            get_focus=lambda: self._focus,
            set_focus=self._set_focus,
            activate_focus=self._activate_focus,
            on_arrow=self._on_arrow,
            cancel_dropdown=self._cancel_dropdown,
            is_dropdown_open=lambda: (
                self.model_dropdown.visible
                or self.sessions_dropdown.visible
                or self.key_dropdown.visible
            ),
            submit_task=self._submit_task,
            scroll_log=self._scroll_log,
        )

        # Build layout
        self.layout = build_layout(
            conversation_log=self.conv_log,
            cwd_text=self.cwd_text,
            session_text=self.session_text,
            more_text=self.more_text,
            model_text=self.model_text,
            key_text=self.key_text,
            input_buffer=self.input_buffer,
            model_dropdown=self.model_dropdown,
            sessions_dropdown=self.sessions_dropdown,
            key_dropdown=self.key_dropdown,
            focus_target=self._focus_target,
        )

        # Build app
        self.app = Application(
            layout=self.layout,
            key_bindings=self._kb,
            full_screen=False,
            mouse_support=True,
        )
        self.app.timeoutlen = 0.05  # Esc 等前缀键更快响应

    def _scroll_log(self, delta: int) -> None:
        """滚动对话日志：负值上滚，正值下滚。"""
        if delta < 0:
            self.conv_log.scroll_up(-delta)
        else:
            self.conv_log.scroll_down(delta)
        self.app.invalidate()

    def _set_focus(self, section: str) -> None:
        self._focus = section
        for i, w in enumerate(self._all_widgets):
            w.set_focused(i == self._focus_map.get(section, -1))
        try:
            if section == "input":
                self.app.layout.focus(self.layout.input_window)
            else:
                self.app.layout.focus(self._focus_target)
        except Exception:
            pass

    def _activate_focus(self) -> None:
        if self._focus == "input":
            self._submit_task(self.input_buffer.text)
        elif self._focus == "more":
            self._toggle_sessions_dropdown()
        elif self._focus == "model":
            self._toggle_model_dropdown()
        elif self._focus == "session":
            self._start_rename()
        elif self._focus == "cwd":
            self._change_directory()
        elif self._focus == "key":
            self._toggle_key_dropdown()

    def _on_arrow(self, direction: int) -> None:
        if self.model_dropdown.visible:
            if direction > 0:
                self.model_dropdown.move_down()
            else:
                self.model_dropdown.move_up()
        elif self.sessions_dropdown and self.sessions_dropdown.visible:
            if direction > 0:
                self.sessions_dropdown.move_down()
            else:
                self.sessions_dropdown.move_up()
        elif self.key_dropdown.visible:
            if direction > 0:
                self.key_dropdown.move_down()
            else:
                self.key_dropdown.move_up()
        self.app.invalidate()

    def _cancel_dropdown(self) -> None:
        if self._pending_mode is not None:
            self._pending_mode = None
            self.input_buffer.text = ""
            self._set_focus("input")
            self.app.invalidate()
            return
        if self.model_dropdown.visible:
            self.model_dropdown.hide()
        if self.sessions_dropdown and self.sessions_dropdown.visible:
            self.sessions_dropdown.hide()
        if self.key_dropdown.visible:
            self.key_dropdown.hide()
        self._set_focus("input")
        self.app.invalidate()

    def _toggle_model_dropdown(self) -> None:
        if self.model_dropdown.visible:
            label, provider = self.model_dropdown.get_selected()
            from hatch.cli import _build_llm
            from hatch.security.key_manager import KeyManager
            km = KeyManager()
            api_key = km.get_key(provider)
            if not api_key:
                self.conv_log._lines.append(
                    f"  No API key for {provider} — model unchanged"
                )
                self.model_dropdown.hide()
                self.app.invalidate()
                return
            import copy
            cand = copy.copy(self.config)
            cand.llm = copy.copy(self.config.llm)
            cand.llm.provider = provider
            cand.llm.model = label
            meta = self.config.llm.providers.get(provider, {})
            cand.llm.api_base = meta.get("api_base", "")
            new_llm = _build_llm(cand, api_key)
            if not new_llm:
                self.conv_log._lines.append(
                    f"  No API key for {provider} — model unchanged"
                )
                self.model_dropdown.hide()
                self.app.invalidate()
                return
            self.llm = new_llm
            self.model_text.update_text(f"{provider}/{label}")
            self.config.llm.provider = provider
            self.config.llm.model = label
            self.model_dropdown.hide()
            self._set_focus("input")
        else:
            self.sessions_dropdown.hide()
            self.model_dropdown.show()
        self.app.invalidate()

    def _toggle_sessions_dropdown(self) -> None:
        sessions = self.session_manager.list_sessions()
        if self.sessions_dropdown and self.sessions_dropdown.visible:
            label, sid = self.sessions_dropdown.get_selected()
            if sid != self.session_id:
                self._switch_session(sid, label)
            self.sessions_dropdown.hide()
            self._set_focus("input")
        else:
            items = [(s.get("task", s["id"])[:20], s["id"]) for s in sessions]
            self.sessions_dropdown.items = items
            self.sessions_dropdown.selected_index = 0
            self.model_dropdown.hide()
            self.sessions_dropdown.show()
        self.app.invalidate()

    def _load_session_history(self) -> None:
        """把会话的历史对话渲染到日志区（全部加载，可滚动浏览）。"""
        turns = self.session_manager.get_conversation_turns(self.session_id, limit=None)
        if not turns:
            return
        self.conv_log.append_text("  ---- previous messages ----")
        for turn in turns:
            content = turn.get("content", "")
            role = turn.get("role", "user")
            if role == "user":
                self.conv_log.append_text(f"\n> {content}")
            else:
                self.conv_log.append_text(content)
        self.conv_log.append_text("  ---- end ----\n")

    def _switch_session(self, sid: str, name: str) -> None:
        self.session_id = sid
        self.session_name = name
        self.is_new = False  # 已有会话，不重新命名
        self.session_text.update_text(name[:15])
        self.conv_log = ConversationLog()
        self.layout = build_layout(
            conversation_log=self.conv_log,
            cwd_text=self.cwd_text,
            session_text=self.session_text,
            more_text=self.more_text,
            model_text=self.model_text,
            key_text=self.key_text,
            input_buffer=self.input_buffer,
            model_dropdown=self.model_dropdown,
            sessions_dropdown=self.sessions_dropdown,
            key_dropdown=self.key_dropdown,
        )
        self.app.layout = self.layout
        self._is_first_reply = True
        self._first_task = ""
        self._first_reply_collected = ""
        self._load_session_history()
        self.app.invalidate()

    def _start_rename(self) -> None:
        self._pending_mode = "rename"
        self.input_buffer.text = self.session_name
        self._set_focus("input")
        self.app.invalidate()

    def _start_key_add(self) -> None:
        """key 导入流程：名称 → API 地址 → 可用模型 → API Key"""
        self._pending_mode = "key_name"
        self._key_add_name = ""
        self._key_add_base = ""
        self._key_add_models = []
        self.input_buffer.text = ""
        self._set_focus("input")
        self.app.invalidate()

    def _handle_key_step(self, text: str) -> None:
        mode = self._pending_mode
        if mode == "key_name":
            name = text.strip()
            if not name:
                self.conv_log.append_text("  Provider name cannot be empty")
                self.app.invalidate()
                return
            self._key_add_name = name
            self._pending_mode = "key_base"
            self.input_buffer.text = ""
            self.app.invalidate()
        elif mode == "key_base":
            base = text.strip()
            if not base:
                known = {
                    "deepseek": "https://api.deepseek.com",
                    "glm": "https://open.bigmodel.cn/api/paas/v4",
                    "claude": "https://api.anthropic.com",
                }
                base = known.get(self._key_add_name, "")
            self._key_add_base = base
            self._pending_mode = "key_models"
            self.input_buffer.text = ""
            self.app.invalidate()
        elif mode == "key_models":
            raw = text.strip()
            models = [m.strip() for m in raw.split(",") if m.strip()]
            if not models:
                models = [self.config.llm.model]
            self._key_add_models = models
            self._pending_mode = "key_key"
            self.input_buffer.text = ""
            self.app.invalidate()
        elif mode == "key_key":
            key = text.strip()
            self._pending_mode = None
            self.input_buffer.text = ""
            if not key:
                self.conv_log.append_text("  Key add cancelled (empty key)")
                self.app.invalidate()
                return
            self.km.set_key(self._key_add_name, key)
            self.km.set_provider_meta(
                self._key_add_name, self._key_add_base, models=self._key_add_models,
            )
            # 同步到内存配置
            self.config.llm.providers.setdefault(self._key_add_name, {})
            self.config.llm.providers[self._key_add_name]["api_base"] = self._key_add_base
            self.config.llm.providers[self._key_add_name]["models"] = self._key_add_models
            # 刷新模型下拉
            self.model_dropdown.items = self._build_model_items()
            self.key_text.update_text(f"key:{self._key_add_name}")
            self.conv_log.append_text(
                f"  Added provider: {self._key_add_name} "
                f"(models: {', '.join(self._key_add_models)})"
            )
            self._set_focus("input")
            self.app.invalidate()

    def _toggle_key_dropdown(self) -> None:
        """key 下拉：查看已有 key / 切换 / 删除 / 新增"""
        if self.key_dropdown.visible:
            action, value = self.key_dropdown.get_selected()
            self.key_dropdown.hide()
            if value == "add":
                self._start_key_add()
            elif value.startswith("switch:"):
                self._switch_provider(value[7:])
            elif value.startswith("delete:"):
                self._delete_provider(value[7:])
            else:
                self._set_focus("input")
        else:
            items = [("+ Add new provider", "add")]
            for p in self.km.list_providers():
                items.append((f"Switch: {p}", f"switch:{p}"))
            for p in self.km.list_providers():
                items.append((f"Delete: {p}", f"delete:{p}"))
            if not items:
                items = [("+ Add new provider", "add")]
            self.key_dropdown.items = items
            self.key_dropdown.selected_index = 0
            self.model_dropdown.hide()
            self.sessions_dropdown.hide()
            self.key_dropdown.show()
        self.app.invalidate()

    def _switch_provider(self, name: str) -> None:
        """切换到已有 key 的 provider"""
        key = self.km.get_key(name)
        if not key:
            self.conv_log.append_text(f"  No key for {name}")
            self._set_focus("input")
            self.app.invalidate()
            return
        from hatch.cli import _build_llm
        import copy
        meta = self.config.llm.providers.get(name, {})
        models = meta.get("models", [])
        model = models[0] if models else self.config.llm.model
        cand = copy.copy(self.config)
        cand.llm = copy.copy(self.config.llm)
        cand.llm.provider = name
        cand.llm.model = model
        cand.llm.api_base = meta.get("api_base", "")
        new_llm = _build_llm(cand, key)
        if not new_llm:
            self.conv_log.append_text(f"  Cannot build LLM for {name}")
            self._set_focus("input")
            self.app.invalidate()
            return
        self.llm = new_llm
        self.config.llm.provider = name
        self.config.llm.model = model
        self.model_text.update_text(f"{name}/{model}")
        self.key_text.update_text(f"key:{name}")
        self.model_dropdown.items = self._build_model_items()
        self.conv_log.append_text(f"  Switched to {name} (model: {model})")
        self._set_focus("input")
        self.app.invalidate()

    def _delete_provider(self, name: str) -> None:
        """删除 provider 的 key 与元信息"""
        self.km.delete_key(name)
        self.km.delete_provider_meta(name)
        self.config.llm.providers.pop(name, None)
        self.model_dropdown.items = self._build_model_items()
        if name == self.config.llm.provider:
            self.conv_log.append_text(
                f"  Deleted {name} — it was the active provider, please switch model/key"
            )
        else:
            self.conv_log.append_text(f"  Deleted {name}")
        self._set_focus("input")
        self.app.invalidate()

    def _change_directory(self) -> None:
        import tkinter.filedialog as fd
        new_dir = fd.askdirectory(initialdir=self.workdir)
        if new_dir and os.path.isdir(new_dir):
            os.chdir(new_dir)
            self.workdir = new_dir
            self.cwd_text.update_text(new_dir[-40:])
            self.session_manager = SessionManager(new_dir)
            sid, is_new = self.session_manager.get_latest_or_create("新对话")
            self.session_id = sid
            self.is_new = is_new
            name = self.session_manager.get_info(sid)
            self.session_name = name["task"] if name else "新对话"
            self.session_text.update_text(self.session_name[:15])
            self.conv_log = ConversationLog()
            self.layout = build_layout(
                conversation_log=self.conv_log,
                cwd_text=self.cwd_text,
                session_text=self.session_text,
                more_text=self.more_text,
                model_text=self.model_text,
                key_text=self.key_text,
                input_buffer=self.input_buffer,
                model_dropdown=self.model_dropdown,
                sessions_dropdown=self.sessions_dropdown,
            key_dropdown=self.key_dropdown,
                focus_target=self._focus_target,
            )
            self.app.layout = self.layout
            self._is_first_reply = True
            self._first_task = ""
            self._first_reply_collected = ""
            self._load_session_history()
            self._set_focus("input")
            self.app.invalidate()

    def _submit_task(self, text: str) -> None:
        if self._pending_mode == "rename":
            name = text.strip() or self.session_name
            self.session_manager.rename(self.session_id, name)
            self.session_name = name
            self.session_text.update_text(name[:15])
            self._pending_mode = None
            self.input_buffer.text = ""
            self.app.invalidate()
            return
        if self._pending_mode in ("key_name", "key_base", "key_models", "key_key"):
            self._handle_key_step(text)
            return
        if not text.strip():
            return
        if self._running_task is not None and not self._running_task.done():
            self.conv_log._lines.append("  Busy — wait for the current task")
            self.app.invalidate()
            return
        task = text.strip()
        self.input_buffer.text = ""
        self.conv_log.follow_tail()  # 新任务开始，滚回底部看最新

        # Save first task for naming
        if self._is_first_reply:
            self._first_task = task

        # Display user input
        self.conv_log._lines.append(f"\n> {task}")
        self.app.invalidate()

        # Build registry
        from hatch.cli import _build_registry
        registry = _build_registry(self.config)

        async def _run():
            try:
                await asyncio.wait_for(
                    run_agent_async(
                        task=task,
                        config=self.config,
                        llm=self.llm,
                        registry=registry,
                        session_manager=self.session_manager,
                        session_id=self.session_id,
                        event_queue=self._event_queue,
                    ),
                    timeout=self.config.tools.test_timeout * 3,
                )
            except asyncio.TimeoutError:
                self.conv_log._lines.append("  Timed out")
                self.app.invalidate()

            # 仅对真正的新会话自动命名（已有会话保持原名字）
            if self.is_new and self._is_first_reply and self._first_reply_collected:
                self._is_first_reply = False
                name_task = asyncio.create_task(self._auto_name())
            else:
                self._is_first_reply = False

            self._set_focus("input")
            self.app.invalidate()

        self._running_task = asyncio.create_task(_run())
        # Start event processor if not already running
        if not hasattr(self, '_event_processor_started'):
            self._event_processor_started = True
            asyncio.create_task(self._process_events())

    async def _process_events(self) -> None:
        """Continuously drain event queue and update display."""
        while True:
            event = await self._event_queue.get()
            if event.get("_done"):
                continue
            self.conv_log.append_event(type("E", (), event)())
            # Track first reply text for naming
            if self._is_first_reply and event.get("type") == "stream_chunk":
                self._first_reply_collected += event.get("text", "")
            self.app.invalidate()

    async def _auto_name(self) -> None:
        """Generate a name for the conversation."""
        name = auto_name(self._first_task, self._first_reply_collected[:500], self.llm)
        self.session_manager.rename(self.session_id, name)
        self.session_name = name
        self.session_text.update_text(name[:15])
        self.app.invalidate()

    async def run(self) -> None:
        """Start the TUI application."""
        # 鼠标模式保活：Windows 控制台失焦/聚焦切换可能丢失鼠标输入模式，
        # 周期性地重新启用，避免"切走再回来滚轮失效"。
        async def _keep_mouse():
            while True:
                await asyncio.sleep(1.0)
                try:
                    self.app.renderer.output.enable_mouse_support()
                except Exception:
                    pass

        asyncio.create_task(_keep_mouse())

        # Show initial greeting
        self.conv_log.append_text(f"  Working directory: {self.workdir}")
        self.conv_log.append_text(f"  Session: {self.session_name}")
        self.conv_log.append_text(f"  Model: {self.config.llm.provider}/{self.config.llm.model}")
        self.conv_log.append_text("")
        if not self.is_new:
            self._load_session_history()
        self.conv_log.append_text("  Tab 切换底部焦点，Enter 激活，Esc 返回输入框")
        self.conv_log.append_text("  工具栏聚焦时 ↑↓ 滚动对话，PgUp/PgDn 翻页")
        self.conv_log.append_text("  Ctrl+E 打开系统编辑器输入（适合中文输入）")
        self.conv_log.append_text("  key 焦点按 Enter 可导入新 provider / API / Key")
        self.conv_log.append_text("  Type a task and press Enter to start.\n")
        self.app.invalidate()

        await self.app.run_async()

    def _build_model_items(self) -> list[tuple[str, str]]:
        """从配置构建模型下拉候选列表（仅含已有 key 的 provider）。"""
        items = []
        for p, meta in self.config.llm.providers.items():
            if self.km.get_key(p) is None:
                continue
            for m in meta.get("models", []):
                items.append((m, p))
        return items
