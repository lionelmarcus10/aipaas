"""Hook helpers — pre-built hook providers for common patterns.

Native Strands v1.53.0 provides HookProvider and HookCallback with events:
  - BeforeToolCallEvent / AfterToolCallEvent
  - BeforeModelCallEvent / AfterModelCallEvent
  - BeforeInvocationEvent / AfterInvocationEvent
  - MessageAddedEvent

These helpers provide ready-to-use hooks for:
  - Circuit breaker (Panne #3)
  - Tool output logging
  - Error tracking
"""

import logging
import time
from typing import Any

from strands.hooks import HookProvider
from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent

logger = logging.getLogger(__name__)


class CircuitBreakerHook(HookProvider):
    """Circuit breaker for tool calls (Panne #3).

    After `failure_threshold` consecutive failures of the same tool,
    calls to that tool are short-circuited with an error for `reset_timeout` seconds.

    Args:
        failure_threshold: Consecutive failures before opening circuit (default 3).
        reset_timeout: Seconds before trying again (default 60).
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    @property
    def registry(self) -> dict:
        return {
            BeforeToolCallEvent: self._on_before,
            AfterToolCallEvent: self._on_after,
        }

    def _on_before(self, event: BeforeToolCallEvent) -> None:
        tool_name = event.tool_name
        open_until = self._open_until.get(tool_name)
        if open_until and time.time() < open_until:
            raise RuntimeError(
                f"Circuit breaker OPEN for tool '{tool_name}' "
                f"(retry after {self.reset_timeout}s)"
            )
        elif open_until:
            # Half-open: reset and try
            self._open_until.pop(tool_name, None)
            self._failures[tool_name] = 0

    def _on_after(self, event: AfterToolCallEvent) -> None:
        result = event.tool_result
        if not isinstance(result, dict):
            return
        tool_name = event.tool_name
        status = result.get("status", "")

        if status == "error":
            count = self._failures.get(tool_name, 0) + 1
            self._failures[tool_name] = count
            if count >= self.failure_threshold:
                self._open_until[tool_name] = time.time() + self.reset_timeout
                logger.warning(
                    "Circuit breaker OPENED for '%s' after %d failures",
                    tool_name, count,
                )
        else:
            self._failures[tool_name] = 0


class ToolLogHook(HookProvider):
    """Log all tool calls and results.

    Args:
        log_level: Logging level (default INFO).
    """

    def __init__(self, log_level: int = logging.INFO) -> None:
        self.log_level = log_level

    @property
    def registry(self) -> dict:
        return {
            BeforeToolCallEvent: self._on_before,
            AfterToolCallEvent: self._on_after,
        }

    def _on_before(self, event: BeforeToolCallEvent) -> None:
        logger.log(self.log_level, "TOOL CALL: %s", event.tool_name)

    def _on_after(self, event: AfterToolCallEvent) -> None:
        result = event.tool_result
        status = result.get("status", "?") if isinstance(result, dict) else "?"
        logger.log(self.log_level, "TOOL RESULT: %s → %s", event.tool_name, status)
