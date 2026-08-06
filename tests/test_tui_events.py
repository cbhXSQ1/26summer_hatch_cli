# tests/test_tui_events.py
from hatch.tui.events import (
    StreamChunk, ToolCall, ToolResult, Feedback, RoundStart,
    RoundEnd, Done, model_new_fields, create_rename_event,
)


class TestEvents:
    def test_stream_chunk_has_text(self):
        e = StreamChunk(text="hello")
        assert e.text == "hello"
        assert e.type == "stream_chunk"

    def test_model_new_fields(self):
        fields = model_new_fields("deepseek-v4-pro", "deepseek")
        assert fields["provider"] == "deepseek"
        assert fields["model"] == "deepseek-v4-pro"

    def test_rename_event(self):
        e = create_rename_event("new-name")
        assert e["new_name"] == "new-name"
        assert e["type"] == "rename_session"
