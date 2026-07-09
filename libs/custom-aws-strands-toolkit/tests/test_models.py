"""Test model providers."""

import os

import pytest

from cast.models import OllamaCloudModel, OpenAICompatModel, from_env


def test_ollama_cloud_model_requires_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OLLAMA_API_KEY"):
        OllamaCloudModel()


def test_ollama_cloud_model_with_key(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key-123")
    model = OllamaCloudModel(model_id="glm-5.2:cloud")
    assert model.config["model_id"] == "glm-5.2:cloud"


def test_from_env_ollama_priority(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-2")
    model = from_env()
    assert isinstance(model, OllamaCloudModel)


def test_from_env_no_provider(monkeypatch):
    for key in ["OLLAMA_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="No model provider"):
        from_env()
