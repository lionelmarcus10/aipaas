"""CAST — Custom AWS Strands Toolkit.

A thin wrapper over AWS Strands Agents (v1.53.0) for rapid agent development.
Uses native Strands features wherever possible, adds helpers only where needed.
"""

from .factory import AgentFactory, create_agent
from .models import BedrockModelWrapper, OllamaCloudModel, OpenAICompatModel, from_env
from .callbacks import AnimatedCallbackHandler
from .sessions import SessionManager
from .skills import PromptLoader, md_to_skill_dirs
from .mcp import MCPRegistry
from .conversation import sliding_window, summarizing, none as no_conversation
from .hooks import CircuitBreakerHook, ToolLogHook
from .memory import local_memory
from .plugins import skills_from_dir, skills_from_md_dir

__version__ = "0.2.0"

__all__ = [
    # Core
    "AgentFactory",
    "create_agent",
    "BedrockModelWrapper",
    "OllamaCloudModel",
    "OpenAICompatModel",
    "from_env",
    "AnimatedCallbackHandler",
    "SessionManager",
    "PromptLoader",
    "md_to_skill_dirs",
    "MCPRegistry",
    # Conversation (Panne #6)
    "sliding_window",
    "summarizing",
    "no_conversation",
    # Hooks (Panne #3, #5)
    "CircuitBreakerHook",
    "ToolLogHook",
    # Memory
    "local_memory",
    # Plugins (native AgentSkills wrapper)
    "skills_from_dir",
    "skills_from_md_dir",
]
