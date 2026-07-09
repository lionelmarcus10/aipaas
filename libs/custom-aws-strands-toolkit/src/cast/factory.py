"""Agent factory — create Strands agents with sensible defaults + native pass-through."""

from typing import Any, Optional

from strands import Agent

from .models import from_env
from .callbacks import AnimatedCallbackHandler
from .sessions import SessionManager
from .skills import PromptLoader
from .mcp import MCPRegistry


class AgentFactory:
    """Factory for creating Strands agents with sensible defaults.

    Handles model, callbacks, sessions, prompts, and MCP automatically.
    All native Strands params (plugins, hooks, memory, conversation_manager,
    sandbox, storage, interventions, structured_output, retry, context_manager)
    are passed through directly.

    Args:
        model: Pre-configured model. If None, auto-detected from env.
        sessions: SessionManager instance. If None, created from env.
        streaming: Enable animated callback handler.
        show_reasoning: Show reasoning tokens in callback.
        prompts_dir: Directory with prompt .md files.
        mcp_config: Path to mcp.json for MCP server plugins.
    """

    def __init__(
        self,
        model: Any = None,
        sessions: SessionManager | None = None,
        streaming: bool = True,
        show_reasoning: bool = True,
        prompts_dir: str | None = None,
        mcp_config: str | None = None,
    ) -> None:
        # If model is explicitly None, try from_env(). If that fails, keep None
        # (mock mode — agent will use fallback responses without an LLM).
        if model is not None:
            self.model = model
        else:
            try:
                self.model = from_env()
            except ValueError:
                self.model = None  # mock mode — no LLM configured
        self.sessions = sessions or SessionManager()
        self.callback = AnimatedCallbackHandler(show_reasoning=show_reasoning) if streaming else None
        self.prompts = PromptLoader(prompts_dir) if prompts_dir else None
        self.mcp = MCPRegistry(mcp_config) if mcp_config else None

    def get_prompt(self, name: str) -> str:
        if not self.prompts:
            raise ValueError("No prompts_dir configured")
        return self.prompts.get_prompt(name)

    def load_mcp_tools(self) -> list[Any]:
        if not self.mcp:
            return []
        return self.mcp.load_all_tools()

    def create_agent(
        self,
        system_prompt: str = "",
        prompt_name: str | None = None,
        tools: list[Any] | None = None,
        session_id: str | None = None,
        include_mcp: bool = True,
        # Native Strands pass-through params
        plugins: list[Any] | None = None,
        hooks: list[Any] | None = None,
        memory_manager: Any = None,
        conversation_manager: Any = None,
        sandbox: Any = None,
        storage: Any = None,
        interventions: list[Any] | None = None,
        structured_output_model: Any = None,
        retry_strategy: Any = None,
        context_manager: Any = None,
        **kwargs: Any,
    ) -> Agent:
        """Create a Strands agent.

        Args:
            system_prompt: Direct system prompt string.
            prompt_name: Load prompt from prompts_dir by name (overrides system_prompt).
            tools: List of @tool decorated functions.
            session_id: Enable session persistence with this ID.
            include_mcp: Include MCP tools from mcp.json.
            plugins: Native Strands plugins (AgentSkills, Steering, etc.).
            hooks: Native Strands hook providers (CircuitBreakerHook, etc.).
            memory_manager: Native MemoryManager for long-term memory.
            conversation_manager: Native SlidingWindow/SummarizingConversationManager.
            sandbox: Native Sandbox for code execution isolation.
            storage: Native Storage (LocalFile, S3, InMemory).
            interventions: Native intervention handlers (Cedar, HITL).
            structured_output_model: Pydantic model for structured output.
            retry_strategy: Native model retry strategy.
            context_manager: 'auto' or 'agentic' context management.
            **kwargs: Extra args passed to Agent().
        """
        if prompt_name:
            system_prompt = self.get_prompt(prompt_name)

        all_tools = list(tools or [])
        if include_mcp and self.mcp:
            all_tools.extend(self.load_mcp_tools())

        session_manager = None
        if session_id:
            session_manager = self.sessions.get_manager(session_id)

        return Agent(
            model=self.model,
            system_prompt=system_prompt,
            tools=all_tools or None,
            session_manager=session_manager,
            callback_handler=self.callback,
            # Native pass-through
            plugins=plugins,
            hooks=hooks,
            memory_manager=memory_manager,
            conversation_manager=conversation_manager,
            sandbox=sandbox,
            storage=storage,
            interventions=interventions,
            structured_output_model=structured_output_model,
            retry_strategy=retry_strategy,
            context_manager=context_manager,
            **kwargs,
        )


def create_agent(
    system_prompt: str = "",
    tools: list[Any] | None = None,
    model: Any = None,
    session_id: str | None = None,
    prompts_dir: str | None = None,
    mcp_config: str | None = None,
    plugins: list[Any] | None = None,
    hooks: list[Any] | None = None,
    memory_manager: Any = None,
    conversation_manager: Any = None,
    sandbox: Any = None,
    storage: Any = None,
    **kwargs: Any,
) -> Agent:
    """Quick-create an agent in one call (convenience wrapper).

    >>> from cast import create_agent
    >>> from strands import tool
    >>>
    >>> @tool
    ... def hello(name: str) -> str:
    ...     return f"Hello {name}!"
    >>>
    >>> agent = create_agent(
    ...     system_prompt="You are a helpful assistant.",
    ...     tools=[hello],
    ... )
    >>> agent("Say hi to Bob")
    """
    factory = AgentFactory(
        model=model,
        prompts_dir=prompts_dir,
        mcp_config=mcp_config,
    )
    return factory.create_agent(
        system_prompt=system_prompt,
        tools=tools,
        session_id=session_id,
        plugins=plugins,
        hooks=hooks,
        memory_manager=memory_manager,
        conversation_manager=conversation_manager,
        sandbox=sandbox,
        storage=storage,
        **kwargs,
    )
