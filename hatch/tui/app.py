# hatch/tui/app.py
"""Main Hatch TUI Application."""

import asyncio
import os
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer

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
    ) -> None:
        self.workdir = workdir
        self.llm = llm
        self.config = config
        self.session_manager = session_manager
        self.session_id = session_id
        self.session_name = session_name

        # Widgets
        self.conv_log = ConversationLog()
        self.cwd_text = FocusableText(workdir[-40:], prefix="")
        self.session_text = FocusableText(session_name[:15], prefix="")
        self.more_text = FocusableText("...", prefix="")
        self.model_text = FocusableText(
            f"{config.llm.provider}/{config.llm.model}", prefix=""
        )
        self.key_text = FocusableText("key", prefix="")

        # Dropdowns
        self.model_dropdown = DropdownMenu(
            items=[
                ("deepseek-v4-pro", "deepseek"),
                ("deepseek-reasoner", "deepseek"),
                ("glm-5.2", "glm"),
                ("glm-4-plus", "glm"),
                ("claude-sonnet-4-20250514", "claude"),
                ("claude-opus-4-20250514", "claude"),
            ],
            title="Select Model",
        )
        self.sessions_dropdown = DropdownMenu(items=[], title="Sessions")

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

        # Input buffer
        self.input_buffer = Buffer(multiline=False)

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
                self.model_dropdown.visible or self.sessions_dropdown.visible
            ),
            submit_task=self._submit_task,
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
        )

        # Build app
        self.app = Application(
            layout=self.layout,
            key_bindings=self._kb,
            full_screen=False,
        )

    def _set_focus(self, section: str) -> None:
        self._focus = section
        for i, w in enumerate(self._all_widgets):
            w.set_focused(i == self._focus_map.get(section, -1))

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
            self._show_key_status()

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
        self.app.invalidate()

    def _cancel_dropdown(self) -> None:
        if self.model_dropdown.visible:
            self.model_dropdown.hide()
        if self.sessions_dropdown and self.sessions_dropdown.visible:
            self.sessions_dropdown.hide()
        self._set_focus("input")
        self.app.invalidate()

    def _toggle_model_dropdown(self) -> None:
        if self.model_dropdown.visible:
            label, provider = self.model_dropdown.get_selected()
            self.model_text.update_text(f"{provider}/{label}")
            self.config.llm.provider = provider
            self.config.llm.model = label
            # Rebuild LLM instance
            from hatch.cli import _build_llm
            from hatch.security.key_manager import KeyManager
            km = KeyManager()
            api_key = km.get_key(provider)
            if api_key:
                new_llm = _build_llm(self.config, api_key)
                if new_llm:
                    self.llm = new_llm
            self.model_dropdown.hide()
        else:
            self.model_dropdown.show()
        self.app.invalidate()

    def _toggle_sessions_dropdown(self) -> None:
        sessions = self.session_manager.list_sessions()
        if self.sessions_dropdown and self.sessions_dropdown.visible:
            label, sid = self.sessions_dropdown.get_selected()
            if sid != self.session_id:
                self._switch_session(sid, label)
            self.sessions_dropdown.hide()
        else:
            items = [(s.get("task", s["id"])[:20], s["id"]) for s in sessions]
            self.sessions_dropdown.items = items
            self.sessions_dropdown.selected_index = 0
            self.sessions_dropdown.show()
        self.app.invalidate()

    def _switch_session(self, sid: str, name: str) -> None:
        self.session_id = sid
        self.session_name = name
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
        )
        self.app.layout = self.layout
        self._is_first_reply = True

    def _start_rename(self) -> None:
        # Use prompt_toolkit's input dialog or simple inline rename
        # For simplicity, use a modal input
        from prompt_toolkit.shortcuts import input_dialog
        async def _do_rename():
            new_name = await input_dialog(
                title="Rename",
                text="Enter new name:",
            ).run_async()
            if new_name:
                self.session_manager.rename(self.session_id, new_name)
                self.session_name = new_name
                self.session_text.update_text(new_name[:15])
                self.app.invalidate()
        asyncio.ensure_future(_do_rename())

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
            )
            self.app.layout = self.layout
            self.app.invalidate()

    def _show_key_status(self) -> None:
        from hatch.security.key_manager import KeyManager
        km = KeyManager()
        providers = km.list_providers()
        if providers:
            status = ", ".join(providers)
            self.key_text.update_text(f"keys: {status}"[:20])
        else:
            self.key_text.update_text("no keys")
        self.app.invalidate()

    def _submit_task(self, text: str) -> None:
        if not text.strip():
            return
        task = text.strip()
        self.input_buffer.text = ""

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

            # Check if first reply for auto-naming
            if self._is_first_reply and self._first_reply_collected:
                self._is_first_reply = False
                name_task = asyncio.ensure_future(self._auto_name())
            else:
                self._is_first_reply = False

            self._set_focus("input")
            self.app.invalidate()

        self._running_task = asyncio.ensure_future(_run())
        # Start event processor if not already running
        if not hasattr(self, '_event_processor_started'):
            self._event_processor_started = True
            asyncio.ensure_future(self._process_events())

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
        # Show initial greeting
        self.conv_log._lines.append(f"  Working directory: {self.workdir}")
        self.conv_log._lines.append(f"  Session: {self.session_name}")
        self.conv_log._lines.append(f"  Model: {self.config.llm.provider}/{self.config.llm.model}")
        self.conv_log._lines.append("  Type a task and press Enter to start.\n")
        self.app.invalidate()

        await self.app.run_async()
