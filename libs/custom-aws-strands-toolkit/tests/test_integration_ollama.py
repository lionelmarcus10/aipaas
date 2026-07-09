"""Integration test with Ollama Cloud (glm-5.2:cloud).

Requires OLLAMA_API_KEY environment variable.
Skips if not set.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OLLAMA_API_KEY"),
    reason="OLLAMA_API_KEY not set — skipping integration test",
)

_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL_ID", "gpt-oss:120b")

from cast import create_agent
from cast.models import OllamaCloudModel
from strands import tool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: First number.
        b: Second number.

    Returns:
        The sum of a and b.
    """
    return a + b


def test_ollama_cloud_basic():
    """Test that Ollama Cloud responds to a simple prompt."""
    model = OllamaCloudModel(model_id=_OLLAMA_MODEL)
    agent = create_agent(
        system_prompt="You are a helpful assistant. Keep answers very short.",
        tools=[add],
        model=model,
        include_mcp=False,
    )
    response = agent("What is 2+3? Use the add tool.")
    assert response is not None
    assert len(str(response)) > 0


def test_ollama_cloud_tool_call():
    """Test that the agent can call a tool via Ollama Cloud."""
    model = OllamaCloudModel(model_id=_OLLAMA_MODEL)
    agent = create_agent(
        system_prompt="You are a math assistant. Always use the add tool for additions.",
        tools=[add],
        model=model,
        include_mcp=False,
    )
    response = agent("What is 10 + 20?")
    text = str(response).lower()
    # The response should contain "30" somewhere
    assert "30" in text, f"Expected '30' in response, got: {response}"
