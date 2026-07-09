"""LLM helper — shared CAST agent factory for the 3 LLM states.

Creates a Strands agent with structured output for JSON responses.
Auto-detects the LLM provider based on environment:

  AWS (Lambda/EKS)  → Amazon Bedrock (Claude Sonnet 4, IAM-based auth)
  k3d / local       → Ollama Cloud (glm-5.2:cloud, OLLAMA_API_KEY)
                    → or vLLM (OpenAI-compatible, VLLM_BASE_URL + VLLM_MODEL_ID)
  OpenRouter        → OpenAI-compatible (GLM-5.2, OPENROUTER_API_KEY)
  No provider       → mock fallback (no LLM, deterministic responses)

The provider is detected by cast.from_env() which checks env vars in order:
  1. AWS_BEDROCK_REGION / AWS_LAMBDA_FUNCTION_NAME → Bedrock
  2. VLLM_BASE_URL → vLLM (OpenAI-compatible endpoint in k3d)
  3. OLLAMA_API_KEY → Ollama Cloud
  4. OPENROUTER_API_KEY → OpenRouter
  5. OPENAI_API_KEY → OpenAI
"""

import json
import os
from pathlib import Path
from typing import Any

from cast import AgentFactory

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Cache the factory to avoid re-creating the model on every call
_factory: AgentFactory | None = None


def get_factory() -> AgentFactory:
    """Get or create the shared AgentFactory.

    Auto-detects the LLM provider via cast.from_env().
    If no provider is configured, uses mock mode (model=None).
    """
    global _factory
    if _factory is None:
        model = None
        # Try to auto-detect provider from environment
        try:
            from cast import from_env
            model = from_env()
        except ValueError:
            # No provider configured — mock mode
            # LLM states will return fallback responses
            pass

        _factory = AgentFactory(
            model=model,
            streaming=False,  # Step Functions doesn't need animated output
            prompts_dir=str(PROMPTS_DIR),
        )
    return _factory


def call_llm(prompt_name: str, user_message: str) -> dict[str, Any]:
    """Call the LLM with a named prompt and return parsed JSON.

    Args:
        prompt_name: Name of the prompt file (e.g. "audit").
        user_message: The user message containing context data.

    Returns:
        Parsed JSON dict from the LLM response.
    """
    factory = get_factory()
    agent = factory.create_agent(
        prompt_name=prompt_name,
    )

    response = agent(user_message)
    text = str(response)

    # Extract JSON from the response (handles markdown code blocks)
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find the first { and last } to extract JSON
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1:
        text = text[first : last + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # If JSON parsing fails, return a fallback
        return {
            "error": "Failed to parse LLM response as JSON",
            "raw_response": text[:500],
        }
