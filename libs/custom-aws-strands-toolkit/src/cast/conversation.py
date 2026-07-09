"""Conversation manager helpers — wrappers for native Strands conversation managers.

Native Strands v1.53.0 provides:
  - SlidingWindowConversationManager (keep last N messages)
  - SummarizingConversationManager (compress old into summary)
  - NullConversationManager (no management)

These helpers create the right manager from a simple config string.
"""

from typing import Any

from strands.agent.conversation_manager import (
    ConversationManager,
    NullConversationManager,
    SlidingWindowConversationManager,
    SummarizingConversationManager,
)


def sliding_window(window_size: int = 40, pin_first: bool = False) -> SlidingWindowConversationManager:
    """Create a sliding window conversation manager.

    Keeps the last `window_size` messages in context, drops older ones.
    Use for Panne #6 (fenêtre glissante).

    Args:
        window_size: Number of recent messages to keep (default 40).
        pin_first: Keep the first message (system prompt) always.
    """
    return SlidingWindowConversationManager(
        window_size=window_size,
        pin_first=pin_first,
    )


def summarizing(
    summary_ratio: float = 0.3,
    preserve_recent: int = 10,
    system_prompt: str | None = None,
) -> SummarizingConversationManager:
    """Create a summarizing conversation manager.

    Compresses old messages into a summary, keeps `preserve_recent` recent ones.
    More token-efficient than sliding window but uses an LLM call for summarization.

    Args:
        summary_ratio: Target ratio of summary length to original (default 0.3).
        preserve_recent: Number of recent messages to keep uncompressed (default 10).
        system_prompt: Custom prompt for the summarization agent.
    """
    return SummarizingConversationManager(
        summary_ratio=summary_ratio,
        preserve_recent_messages=preserve_recent,
        summarization_system_prompt=system_prompt,
    )


def none() -> NullConversationManager:
    """Disable conversation management (unlimited context)."""
    return NullConversationManager()
