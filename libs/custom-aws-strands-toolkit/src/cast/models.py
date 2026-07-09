"""Model providers — Bedrock, Ollama Cloud, OpenAI-compatible, env-based factory.

Provider priority (from_env):
  1. AWS_BEDROCK_REGION or AWS_LAMBDA_FUNCTION_NAME → BedrockModel (IAM-based, no API key)
  2. OLLAMA_API_KEY  → OllamaCloudModel (Ollama Cloud)
  3. OPENROUTER_API_KEY → OpenAICompatModel (OpenRouter)
  4. OPENAI_API_KEY  → OpenAICompatModel (OpenAI)
"""

import os
from typing import Any

from strands.models.ollama import OllamaModel
from strands.models.openai import OpenAIModel


class BedrockModelWrapper:
    """AWS Bedrock model wrapper — uses IAM role for auth (no API key needed).

    On AWS (Lambda, EKS, EC2), the Lambda/pod IAM role automatically provides
    Bedrock permissions via boto3. No API key or token needed.

    Default model: Claude Sonnet 4 (global.anthropic.claude-sonnet-4-6).
    Override with BEDROCK_MODEL_ID env var.

    Usage:
      model = BedrockModelWrapper()  # auto-detects region from env
      agent = Agent(model=model, ...)

    Or via from_env():
      model = from_env()  # returns BedrockModelWrapper if on AWS
    """

    def __init__(
        self,
        model_id: str | None = None,
        region_name: str | None = None,
        **config: Any,
    ) -> None:
        from strands.models.bedrock import BedrockModel

        model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID",
            "global.anthropic.claude-sonnet-4-6",
        )
        region_name = region_name or os.environ.get(
            "AWS_BEDROCK_REGION",
            os.environ.get("AWS_REGION", "us-west-2"),
        )

        self._model = BedrockModel(
            model_id=model_id,
            region_name=region_name,
            # Default to non-streaming (Converse API).
            # Floci/LocalStack don't support ConverseStream.
            # Real AWS supports both, but Step Functions doesn't need streaming.
            streaming=config.pop("streaming", False),
            **config,
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the underlying BedrockModel."""
        return getattr(self._model, name)


class OllamaCloudModel(OllamaModel):
    """Ollama Cloud model (https://ollama.com) with Bearer token auth.

    Uses the native Strands OllamaModel under the hood, just configures
    the host and auth headers for Ollama Cloud.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str = "glm-5.2:cloud",
        host: str = "https://ollama.com",
        **config: Any,
    ) -> None:
        api_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
        if not api_key:
            raise ValueError("OLLAMA_API_KEY required (set env var or pass api_key=)")
        super().__init__(
            host=host,
            model_id=model_id,
            ollama_client_args={"headers": {"Authorization": f"Bearer {api_key}"}},
            **config,
        )


class OpenAICompatModel(OpenAIModel):
    """OpenAI-compatible model for custom endpoints (OpenRouter, vLLM, etc.).

    Preserves reasoning_content for models that return it (GLM, DeepSeek-R1).
    Also strips empty tools arrays from requests (vLLM rejects `tools: []`).
    """

    @classmethod
    def format_request_message_content(cls, content: dict[str, Any]) -> dict[str, Any]:
        if "reasoningContent" in content:
            text = content["reasoningContent"].get("text", "")
            return {"type": "text", "text": text}
        return super().format_request_message_content(content)

    def format_request(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Override to strip empty tools array (vLLM rejects `tools: []`)."""
        request = super().format_request(*args, **kwargs)
        if not request.get("tools"):
            request.pop("tools", None)
        return request


def from_env() -> BedrockModelWrapper | OllamaCloudModel | OpenAICompatModel:
    """Auto-detect provider from environment variables.

    Priority (first match wins):
      0. LLM_PROVIDER=bedrock|ollama|vllm|openrouter|openai  (explicit override)
      1. AWS_BEDROCK_REGION set, or running on AWS Lambda/EKS
         → BedrockModelWrapper (IAM-based auth, no API key needed)
      2. VLLM_BASE_URL → OpenAICompatModel (vLLM endpoint in k3d, no API key needed)
      3. OLLAMA_API_KEY  → OllamaCloudModel (model: OLLAMA_MODEL_ID or glm-5.2:cloud)
      4. OPENROUTER_API_KEY → OpenAICompatModel (base_url: openrouter, model: SCENARIO_MODEL_ID)
      5. OPENAI_API_KEY  → OpenAICompatModel (model: OPENAI_MODEL_ID or gpt-4o)

    Use LLM_PROVIDER to force a specific provider regardless of auto-detection.
    This is needed on Lambda where AWS_LAMBDA_FUNCTION_NAME is always set by the
    runtime, which would otherwise always trigger Bedrock.
    """
    # 0. Explicit override — highest priority
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if provider == "bedrock":
        return BedrockModelWrapper()
    if provider == "ollama":
        return OllamaCloudModel(
            model_id=os.environ.get("OLLAMA_MODEL_ID", "glm-5.2:cloud"),
        )
    if provider == "vllm":
        return OpenAICompatModel(
            client_args={
                "api_key": os.environ.get("VLLM_API_KEY", "dummy"),
                "base_url": os.environ["VLLM_BASE_URL"],
            },
            model_id=os.environ.get("VLLM_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct"),
            params={"temperature": 0.3},
        )
    if provider == "openrouter":
        return OpenAICompatModel(
            client_args={
                "api_key": os.environ["OPENROUTER_API_KEY"],
                "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            },
            model_id=os.environ.get("SCENARIO_MODEL_ID", "z-ai/glm-5.2"),
            params={"temperature": 0.7},
        )
    if provider == "openai":
        return OpenAICompatModel(
            client_args={"api_key": os.environ["OPENAI_API_KEY"]},
            model_id=os.environ.get("OPENAI_MODEL_ID", "gpt-4o"),
            params={"temperature": 0.7},
        )

    # 1. Bedrock — detect AWS environment (Lambda, EKS, EC2)
    if (
        os.environ.get("AWS_BEDROCK_REGION")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or (os.environ.get("AWS_REGION") and os.environ.get("AWS_EXECUTION_ENV"))
    ):
        return BedrockModelWrapper()

    # 2. vLLM — OpenAI-compatible endpoint (k3d local inference)
    #    VLLM_BASE_URL = http://vllm-svc.aipaas.svc.cluster.local:80/v1
    #    VLLM_MODEL_ID = Qwen/Qwen2.5-1.5B-Instruct
    if os.environ.get("VLLM_BASE_URL"):
        return OpenAICompatModel(
            client_args={
                "api_key": os.environ.get("VLLM_API_KEY", "dummy"),  # vLLM doesn't check the key
                "base_url": os.environ["VLLM_BASE_URL"],
            },
            model_id=os.environ.get("VLLM_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct"),
            params={"temperature": 0.3},
        )

    # 3. Ollama Cloud
    if os.environ.get("OLLAMA_API_KEY"):
        return OllamaCloudModel(
            model_id=os.environ.get("OLLAMA_MODEL_ID", "glm-5.2:cloud"),
        )

    # 4. OpenRouter
    if os.environ.get("OPENROUTER_API_KEY"):
        return OpenAICompatModel(
            client_args={
                "api_key": os.environ["OPENROUTER_API_KEY"],
                "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            },
            model_id=os.environ.get("SCENARIO_MODEL_ID", "z-ai/glm-5.2"),
            params={"temperature": 0.7},
        )

    # 5. OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAICompatModel(
            client_args={"api_key": os.environ["OPENAI_API_KEY"]},
            model_id=os.environ.get("OPENAI_MODEL_ID", "gpt-4o"),
            params={"temperature": 0.7},
        )

    raise ValueError(
        "No model provider configured. Set LLM_PROVIDER=bedrock|ollama|vllm|openrouter|openai, "
        "or one of: AWS_BEDROCK_REGION (Bedrock), VLLM_BASE_URL (vLLM), "
        "OLLAMA_API_KEY (Ollama), OPENAI_API_KEY, OPENROUTER_API_KEY"
    )
