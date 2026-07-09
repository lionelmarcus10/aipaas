"""Test conversation manager helpers."""

from cast.conversation import sliding_window, summarizing
from cast.conversation import none as no_conversation

from strands.agent.conversation_manager import (
    SlidingWindowConversationManager,
    SummarizingConversationManager,
    NullConversationManager,
)


def test_sliding_window():
    cm = sliding_window(window_size=20)
    assert isinstance(cm, SlidingWindowConversationManager)


def test_sliding_window_pin_first():
    cm = sliding_window(window_size=10, pin_first=True)
    assert isinstance(cm, SlidingWindowConversationManager)


def test_summarizing():
    cm = summarizing(summary_ratio=0.5, preserve_recent=5)
    assert isinstance(cm, SummarizingConversationManager)


def test_none():
    cm = no_conversation()
    assert isinstance(cm, NullConversationManager)
