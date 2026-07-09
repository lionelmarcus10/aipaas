"""Animated callback handler — streaming with reasoning + tool indicators."""

import sys
import threading
from typing import Any


class AnimatedCallbackHandler:
    """Streams reasoning (dimmed) and text output with tool-call spinners.

    Args:
        show_reasoning: Show reasoning tokens in dimmed style.
        verbose_tools: Announce each tool call with a spinner indicator.
    """

    _SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, show_reasoning: bool = True, verbose_tools: bool = True) -> None:
        self.show_reasoning = show_reasoning
        self.verbose_tools = verbose_tools
        self._in_reasoning = False
        self._in_text = False
        self._tool_count = 0
        self._spin_idx = 0
        self._lock = threading.Lock()

    def __call__(self, **kwargs: Any) -> None:
        with self._lock:
            reasoning = kwargs.get("reasoningText", False)
            data = kwargs.get("data", "")
            complete = kwargs.get("complete", False)
            tool_use = (
                kwargs.get("event", {})
                .get("contentBlockStart", {})
                .get("start", {})
                .get("toolUse")
            )

            # Reset at start of event loop
            if kwargs.get("init_event_loop"):
                self._in_reasoning = self._in_text = False
                self._tool_count = 0
                return
            if kwargs.get("start_event_loop"):
                print()
                return

            # Reasoning tokens (dimmed)
            if reasoning and self.show_reasoning:
                if not self._in_reasoning:
                    self._in_reasoning = True
                    self._in_text = False
                    print("\033[2m", end="", flush=True)
                print(reasoning, end="", flush=True)
                return

            # Text output
            if data:
                if self._in_reasoning:
                    print("\033[0m", end="", flush=True)
                    self._in_reasoning = False
                if not self._in_text:
                    self._in_text = True
                    print()
                print(data, end="" if not complete else "\n", flush=True)

            # Tool call announcement
            if tool_use and self.verbose_tools:
                if self._in_reasoning:
                    print("\033[0m", end="", flush=True)
                    self._in_reasoning = False
                self._tool_count += 1
                name = tool_use.get("name", "unknown")
                print(f"\n\033[36m  ⚡ Tool #{self._tool_count}: {name}\033[0m", flush=True)

            # End of message
            if complete:
                if self._in_reasoning:
                    print("\033[0m", end="", flush=True)
                    self._in_reasoning = False
                if self._in_text:
                    print()
                    self._in_text = False
