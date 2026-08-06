"""TUI event types passed through asyncio.Queue."""

from dataclasses import dataclass, field
from enum import Enum


class ToolbarSection(Enum):
    CWD = "cwd"
    SESSION = "session"
    MORE = "more"
    MODEL = "model"
    KEY = "key"
    INPUT = "input"


@dataclass
class StreamChunk:
    type: str = "stream_chunk"
    text: str = ""


@dataclass
class ToolCall:
    type: str = "tool_call"
    name: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    type: str = "tool_result"
    name: str = ""
    success: bool = True
    output: str = ""


@dataclass
class Feedback:
    type: str = "feedback"
    success: bool = True
    issues: int = 0
    context: str = ""


@dataclass
class RoundStart:
    type: str = "round_start"
    round: int = 0
    max_rounds: int = 3


@dataclass
class RoundEnd:
    type: str = "round_end"
    round: int = 0
    all_ok: bool = False


@dataclass
class Done:
    type: str = "done"
    status: str = ""
    rounds: int = 0


@dataclass
class Warning:
    type: str = "warning"
    msg: str = ""


# Union type for queue
TUIEvent = StreamChunk | ToolCall | ToolResult | Feedback | RoundStart | RoundEnd | Done | Warning


def model_new_fields(model_name: str, provider: str) -> dict:
    """Create event dict for model change."""
    return {"type": "model_changed", "model": model_name, "provider": provider}


def create_rename_event(new_name: str) -> dict:
    """Create event dict for session rename."""
    return {"type": "rename_session", "new_name": new_name}
