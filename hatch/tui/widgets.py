"""TUI widgets: FocusableText, DropdownMenu, ConversationLog."""

import re

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension


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


class LogControl(FormattedTextControl):
    """对话日志控制：控制层拦截滚轮事件（任意位置），并捕获窗口高度。"""

    def __init__(self, log: "ConversationLog", text) -> None:
        self.log = log
        super().__init__(text=text)

    def create_content(self, width: int, height: int | None):
        # 在渲染前捕获日志窗口高度，供 _text 切片使用
        # （布局计算阶段 height 可能为 None，此时保持上一次的值）
        if height is not None:
            self.log._last_h = max(1, height)
        return super().create_content(width, height)

    def mouse_handler(self, mouse_event):
        from prompt_toolkit.mouse_events import MouseEventType

        if mouse_event.event_type in (
            MouseEventType.SCROLL_UP,
            MouseEventType.SCROLL_DOWN,
        ):
            self.log._mouse_handler(mouse_event)
            return None
        return super().mouse_handler(mouse_event)


class ConversationLog:
    """Scrollable conversation history area.

    滚动模型：scroll_top 指定可见窗口首行；光标锚定在窗口末行
    (scroll_top + H - 1)，由 prompt_toolkit 的 do_scroll 推导出
    精确的 vertical_scroll。任何方向滚动都即时生效，无死区。
    """

    def __init__(self, max_lines: int | None = None) -> None:
        self._lines: list[str] = []
        self.max_lines = max_lines  # None = 不限制，全部保留可滚动
        # 流式过滤 ```json ... ``` 代码块的状态（可能跨多个 chunk）
        self._json_fence: str | None = None
        self._pending_ticks: str = ""
        # 滚动状态
        self._scroll_top = 0       # 可见窗口首行
        self._follow = True        # 是否跟随底部
        self._last_h = 20          # 窗口高度（渲染时更新）

    def _trim(self) -> None:
        if self.max_lines and len(self._lines) > self.max_lines:
            drop = len(self._lines) - self.max_lines
            self._lines = self._lines[-self.max_lines:]
            self._scroll_top = max(0, self._scroll_top - drop)

    def append_event(self, event) -> None:
        t = getattr(event, "type", None)
        if t == "stream_chunk":
            self._append_stream(getattr(event, "text", ""))
        else:
            text = self._format(event)
            if text:
                for line in text.split("\n"):
                    self._lines.append(line)
        self._trim()

    def scroll_up(self, step: int = 1) -> None:
        n = len(self._lines)
        if n == 0:
            return
        if self._follow:
            self._follow = False
            self._scroll_top = max(0, n - self._last_h)
        self._scroll_top = max(0, self._scroll_top - step)

    def scroll_down(self, step: int = 1) -> None:
        n = len(self._lines)
        if n == 0 or self._follow:
            return  # 已在底部
        self._scroll_top += step
        if self._scroll_top + self._last_h >= n:
            self._follow = True  # 回到跟随底部

    def follow_tail(self) -> None:
        self._follow = True

    def at_tail(self) -> bool:
        return self._follow

    def _effective_scroll(self, n: int) -> int:
        if self._follow:
            return max(0, n - self._last_h)
        return max(0, min(self._scroll_top, n - 1))

    def _get_visible_lines(self, lines: list[str]) -> tuple[list[str], int]:
        """切片：返回 (可见行, 光标所在行偏移)。"""
        n = len(lines)
        if n == 0:
            return [], 0
        s = self._effective_scroll(n)
        end = min(n, s + self._last_h)
        visible = lines[s:end]
        # 光标锚定切片末行：内容高度==窗口高度时无需滚动，视图=切片
        cursor = len(visible) - 1
        return visible, cursor

    def _mouse_handler(self, mouse_event):
        """滚轮处理器：注册在每个文本片段上。
        返回 None 表示已处理并触发重绘。
        """
        from prompt_toolkit.application import get_app
        from prompt_toolkit.mouse_events import MouseEventType

        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll_up(3)
            get_app().invalidate()
            return None
        if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll_down(3)
            get_app().invalidate()
            return None
        return NotImplemented

    def append_event(self, event) -> None:
        t = getattr(event, "type", None)
        if t == "stream_chunk":
            self._append_stream(getattr(event, "text", ""))
        else:
            text = self._format(event)
            if text:
                for line in text.split("\n"):
                    self._lines.append(line)
        self._trim()

    def _append_lines(self, text: str) -> None:
        """按行追加文本，首段接续当前行。"""
        parts = text.split("\n")
        if self._lines:
            self._lines[-1] += parts[0]
        else:
            self._lines.append(parts[0])
        for p in parts[1:]:
            self._lines.append(p)

    def _append_stream(self, text: str) -> None:
        """追加流式文本到当前行，过滤 ```json``` 代码块，遇到换行才断行。"""
        if not text:
            return

        # 正在 json 代码块内：丢弃直到闭合
        if self._json_fence is not None:
            self._json_fence += text
            end = self._json_fence.find("```")
            if end != -1:
                self._json_fence = None
            return

        # 拼接缓存的尾部反引号（可能是 ```json 的跨 chunk 开头）
        if self._pending_ticks:
            text = self._pending_ticks + text
            self._pending_ticks = ""

        low = text.lower()
        idx = low.find("```json")
        if idx != -1:
            if idx > 0:
                self._append_lines(text[:idx])
            rest = text[idx + 6:]
            end = rest.find("```")
            if end != -1:
                self._append_lines(rest[end + 3:])
            else:
                self._json_fence = rest
            return

        # 末尾反引号可能是 ```json 的跨 chunk 开头，先缓存
        if text.endswith("`"):
            m = re.search(r"(`+)$", text)
            ticks = m.group(1)
            body = text[: m.start()]
            if body:
                self._append_lines(body)
            self._pending_ticks = ticks
            return

        self._append_lines(text)

    def append_text(self, text: str) -> None:
        """追加普通文本（按行拆分），用于历史消息加载等。"""
        if not text:
            return
        for line in text.split("\n"):
            self._lines.append(line)
        self._trim()

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
            lines = self.get_text().split("\n")
            visible, cursor = self._get_visible_lines(lines)
            if not visible:
                return []
            fragments = []
            for i, line in enumerate(visible):
                if i == cursor:
                    fragments.append(("[SetCursorPosition]", ""))
                if i > 0:
                    fragments.append(("", "\n"))
                fragments.append(("", line))
            return fragments

        return Window(
            content=LogControl(self, _text),
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
    """Float dropdown list for More/Model/Key selection. Keyboard-navigable."""

    def __init__(self, items: list[tuple[str, str]], title: str = "") -> None:
        """
        items: list of (display_label, value)
        """
        self.items = items
        self.title = title
        self.selected_index = 0
        self.visible = False
        self._window: Window | None = None

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
        # 行间插入换行：无分隔时 prompt_toolkit 把所有项拼成一行
        fragments = []
        for style, text in lines:
            if fragments:
                fragments.append(("", "\n"))
            fragments.append((style, text))
        return fragments

    def __pt_container__(self):
        # 缓存窗口：全宽 + 不透明背景，完整覆盖底层对话文本
        if self._window is None:
            self._window = Window(
                content=FormattedTextControl(
                    text=lambda: self._get_formatted_lines() if self.visible else [],
                ),
                # 隐藏时高度为 0：浮层整体跳过绘制，不会用背景行
                # 覆盖其它可见下拉（多个下拉全宽堆在 top=0 互相遮盖）。
                height=lambda: None if self.visible else Dimension.zero(),
                style="bg:#1a1a1a",
                dont_extend_height=True,
            )
        return self._window
