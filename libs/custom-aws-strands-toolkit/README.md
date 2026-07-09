# CAST — Custom AWS Strands Toolkit

A thin wrapper over [AWS Strands Agents](https://strandsagents.com) (v1.53.0) for rapid agent development.

> Uses native Strands features wherever possible. Adds helpers only where Strands doesn't cover the gap.

## What CAST does vs what Strands does natively

| Feature | Native Strands | CAST adds |
|---------|---------------|-----------|
| Model providers (Ollama, OpenAI, Bedrock...) | ✅ | Ollama Cloud auth, reasoning_content preservation, env auto-detect |
| Callback handlers | ✅ (PrintingCallbackHandler) | AnimatedCallbackHandler (reasoning + spinners) |
| Session management | ✅ (File, S3, Snapshot) | save() in-memory agent to disk |
| Skills (SKILL.md) | ✅ (AgentSkills plugin) | md→SKILL.md converter, flat .md loader |
| Prompts from files | ❌ | PromptLoader (load .md by name) |
| MCP servers | ✅ (MCPClient) | JSON config (like Windsurf/VSCode mcp.json) |
| Conversation managers | ✅ (Sliding, Summarizing) | Helper functions |
| Hooks | ✅ (HookProvider) | CircuitBreakerHook, ToolLogHook |
| Memory | ✅ (MemoryManager) | local_memory() preset |
| Plugins | ✅ (AgentSkills, Steering...) | skills_from_md_dir() helper |
| CLI REPL | ❌ | Interactive loop with /save, /sessions |

## Install

```bash
uv add cast
# or
pip install cast
```

## Quick Start

```python
from cast import create_agent
from strands import tool

@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

agent = create_agent(
    system_prompt="You are a math assistant.",
    tools=[add],
)

response = agent("What is 10 + 20?")
```

## Model Providers

Auto-detected from environment:

| Env Var | Provider | Default Model |
|---------|----------|---------------|
| `OLLAMA_API_KEY` | Ollama Cloud | `gpt-oss:120b` |
| `OPENROUTER_API_KEY` | OpenRouter | `z-ai/glm-5.2` |
| `OPENAI_API_KEY` | OpenAI | `gpt-4o` |

```python
from cast.models import OllamaCloudModel, OpenAICompatModel, from_env

# Auto-detect
model = from_env()

# Manual
model = OllamaCloudModel(model_id="gpt-oss:120b")
model = OpenAICompatModel(
    client_args={"api_key": "xxx", "base_url": "https://openrouter.ai/api/v1"},
    model_id="z-ai/glm-5.2",
)
```

## Prompts (from markdown)

No native Strands equivalent. Load .md files by name:

```
prompts/
├── assistant.md  → prompt "assistant"
├── auditor.md    → prompt "auditor"
└── patcher.md     → prompt "patcher"
```

```python
from cast import AgentFactory

factory = AgentFactory(prompts_dir="prompts/")
agent = factory.create_agent(prompt_name="auditor", tools=[...])
```

## Skills (native AgentSkills + CAST converter)

Strands v1.53.0 has a native `AgentSkills` plugin that reads `SKILL.md` files.
CAST provides a converter for flat .md files:

```python
from cast import skills_from_md_dir

# Load flat .md files as native AgentSkills plugin
plugin = skills_from_md_dir("skills/")  # reads youtuber.md, coder.md, etc.
agent = create_agent(plugins=[plugin], system_prompt="...")
```

Or convert to SKILL.md directory structure (one-time):

```python
from cast import md_to_skill_dirs

md_to_skill_dirs("flat_skills/", "skill_dirs/")
# flat_skills/youtuber.md → skill_dirs/youtuber/SKILL.md

from strands.vended_plugins.skills import AgentSkills
plugin = AgentSkills(skills=["skill_dirs/"])
```

## MCP Servers (from JSON)

```json
// mcp.json
{
  "brightdata": {
    "url": "https://mcp.brightdata.com/mcp?token=xxx",
    "transport": "streamable_http"
  },
  "filesystem": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
    "transport": "stdio"
  }
}
```

```python
from cast import AgentFactory

factory = AgentFactory(mcp_config="mcp.json")
agent = factory.create_agent(
    system_prompt="You are a research assistant.",
    tools=[my_tool],
    include_mcp=True,
)
```

## Conversation Management (Panne #6)

```python
from cast import sliding_window, summarizing, create_agent

# Sliding window: keep last 40 messages
agent = create_agent(
    system_prompt="...",
    conversation_manager=sliding_window(window_size=40),
)

# Summarizing: compress old messages into summary
agent = create_agent(
    system_prompt="...",
    conversation_manager=summarizing(summary_ratio=0.3, preserve_recent=10),
)
```

## Hooks (Panne #3 Circuit Breaker, logging)

```python
from cast import CircuitBreakerHook, ToolLogHook, create_agent

agent = create_agent(
    system_prompt="...",
    tools=[scan_repo, apply_patch],
    hooks=[
        CircuitBreakerHook(failure_threshold=3, reset_timeout=60),
        ToolLogHook(),
    ],
)
```

## Memory (long-term, cross-session)

```python
from cast import local_memory, create_agent

agent = create_agent(
    system_prompt="...",
    memory_manager=local_memory(name="agent-notes"),
)
```

## Sessions

```python
from cast import AgentFactory

factory = AgentFactory()

# With session persistence
agent = factory.create_agent(
    system_prompt="You are helpful.",
    session_id="my-session",
)

# Save current conversation
factory.sessions.save(agent, "my-session")

# List saved sessions
print(factory.sessions.list())
```

## Full AgentFactory (all native pass-through)

```python
from cast import AgentFactory, sliding_window, CircuitBreakerHook, local_memory, skills_from_md_dir

factory = AgentFactory(
    prompts_dir="prompts/",
    mcp_config="mcp.json",
    streaming=True,
)

agent = factory.create_agent(
    prompt_name="auditor",          # load from prompts/
    tools=[parse_invoice, compute_variance],
    session_id="session-1",
    # Native Strands pass-through:
    plugins=[skills_from_md_dir("skills/")],
    hooks=[CircuitBreakerHook()],
    memory_manager=local_memory(),
    conversation_manager=sliding_window(window_size=40),
    structured_output_model=AuditResult,  # Pydantic model
    context_manager="auto",
)
```

## CLI REPL

```python
from cast import AgentFactory
from cast.cli import run_cli

factory = AgentFactory(prompts_dir="prompts/")
run_cli(factory, system_prompt="You are helpful.", tools=[my_tool])
```

## API Reference

### Core
- `create_agent(...)` — quick-create in one call
- `AgentFactory(...)` — factory with shared config
- `OllamaCloudModel(api_key, model_id, host)` — Ollama Cloud with auth
- `OpenAICompatModel(client_args, model_id, params)` — OpenAI-compatible with reasoning_content
- `from_env()` — auto-detect provider
- `AnimatedCallbackHandler(show_reasoning, verbose_tools)` — streaming UI
- `SessionManager(storage_dir)` — save/resume/list sessions
- `PromptLoader(prompts_dir)` — load .md prompts by name
- `MCPRegistry(config_path)` — MCP servers from JSON

### Skills
- `md_to_skill_dirs(md_dir, output_dir)` — convert flat .md → SKILL.md dirs
- `skills_from_md_dir(md_dir)` — create native AgentSkills from flat .md
- `skills_from_dir(skills_dir)` — create native AgentSkills from SKILL.md dirs

### Conversation (Panne #6)
- `sliding_window(window_size, pin_first)` — SlidingWindowConversationManager
- `summarizing(summary_ratio, preserve_recent, system_prompt)` — SummarizingConversationManager
- `no_conversation()` — NullConversationManager

### Hooks (Panne #3, #5)
- `CircuitBreakerHook(failure_threshold, reset_timeout)` — opens circuit after N failures
- `ToolLogHook(log_level)` — logs all tool calls

### Memory
- `local_memory(name, add_tool)` — TestMemoryStore + MemoryManager

## Testing

```bash
# Unit tests only
uv run pytest tests/ -k "not integration"

# With Ollama Cloud integration
OLLAMA_API_KEY="your-key" uv run pytest tests/ -v
```
