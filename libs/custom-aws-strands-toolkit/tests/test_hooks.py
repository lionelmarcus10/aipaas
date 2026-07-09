"""Test hooks — CircuitBreakerHook and ToolLogHook."""

from cast.hooks import CircuitBreakerHook, ToolLogHook


def test_circuit_breaker_init():
    hook = CircuitBreakerHook(failure_threshold=3, reset_timeout=30)
    assert hook.failure_threshold == 3
    assert hook.reset_timeout == 30


def test_circuit_breaker_registry():
    hook = CircuitBreakerHook()
    reg = hook.registry
    assert len(reg) == 2  # Before + After tool call


def test_tool_log_hook_init():
    hook = ToolLogHook()
    assert hook.log_level == 20  # logging.INFO


def test_tool_log_hook_registry():
    hook = ToolLogHook()
    reg = hook.registry
    assert len(reg) == 2
