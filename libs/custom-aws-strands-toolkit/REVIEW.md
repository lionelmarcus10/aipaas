# CAST Review — Native Strands Features vs CAST Wrappers

> Based on Strands v1.53.0 source code introspection + official docs.
> Generated after installing `strands-agents-mcp-server` v0.2.9 and analyzing the SDK.

---

## Summary Verdict

| CAST Module | Verdict | Action |
|-------------|---------|--------|
| `models.py` | ✅ **KEEP** — adds real value | OllamaCloudModel wraps auth headers, OpenAICompatModel preserves reasoning_content. Native Strands doesn't do this. |
| `callbacks.py` | ✅ **KEEP** — adds real value | AnimatedCallbackHandler is custom UX. Native only has PrintingCallbackHandler. |
| `sessions.py` | ⚠️ **SIMPLIFY** — native has more | Strands now has `FileSessionManager`, `S3SessionManager`, `SnapshotSessionManager`. CAST's SessionManager.save() is still useful (saves in-memory agent to disk) but should delegate more. |
| `skills.py` (SkillLoader) | ❌ **DELETE** — replaced by native | Strands v1.53.0 has `AgentSkills` plugin that reads SKILL.md from directories natively. CAST's SkillLoader is redundant. |
| `skills.py` (PromptLoader) | ✅ **KEEP** — no native equivalent | Strands has no "load prompt from .md file by name" feature. PromptLoader is genuinely useful. |
| `mcp.py` | ⚠️ **SIMPLIFY** — native MCPClient exists | Strands has `MCPClient` natively. CAST's MCPRegistry adds JSON config (like Windsurf/VSCode) which is useful, but should use native MCPClient more directly. |
| `factory.py` | ⚠️ **REFACTOR** — expose native features | AgentFactory should pass through native params (plugins, hooks, memory, conversation_manager, sandbox, storage) instead of hiding them. |
| `cli.py` | ✅ **KEEP** — no native equivalent | Strands has no built-in REPL. |

---

## Detailed Analysis per Module

### 1. `cast.models` — KEEP ✅

**What CAST does:** OllamaCloudModel (Bearer auth), OpenAICompatModel (reasoning_content), from_env().

**What Strands native has:**
- `OllamaModel(host, model_id, ollama_client_args)` — native, but NO built-in Cloud auth
- `OpenAIModel(client_args, model_id, params)` — native, but DROPS reasoning_content

**Verdict:** CAST adds genuine value here. The native `OllamaModel` doesn't configure Bearer token auth for Ollama Cloud automatically. The native `OpenAIModel` drops `reasoning_content` which breaks multi-turn with GLM/DeepSeek-R1.

**No changes needed.**

---

### 2. `cast.callbacks` — KEEP ✅

**What CAST does:** AnimatedCallbackHandler with reasoning display + tool spinners.

**What Strands native has:**
- `PrintingCallbackHandler()` — basic print, no reasoning, no spinners
- Custom callback functions — you write your own

**Verdict:** CAST's AnimatedCallbackHandler is genuinely better UX than the native default. No native equivalent exists.

**No changes needed.**

---

### 3. `cast.sessions` — SIMPLIFY ⚠️

**What CAST does:** SessionManager with save/resume/list.

**What Strands native has (v1.53.0):**
- `FileSessionManager(session_id, storage_dir)` — local disk sessions
- `S3SessionManager(session_id, bucket, prefix)` — S3 sessions (NEW)
- `SnapshotSessionManager(session_id, storage, save_latest_on)` — snapshot-based sessions (NEW)
- `SaveLatestStrategy` — auto-save latest
- `SnapshotTrigger` — trigger snapshots on events

**What CAST's SessionManager.save() does that native doesn't:**
- Saves an in-memory agent's messages to disk (the native FileSessionManager works differently — it's used during agent lifecycle, not for post-hoc saving)

**Verdict:** Keep `save()` method (useful for saving after a non-persistent session). But `get_manager()` and `list()` should just delegate to native classes. Add S3 support via native `S3SessionManager`.

**Refactor:**
```python
# BEFORE (CAST creates its own FileSessionManager wrapper)
def get_manager(self, session_id):
    return FileSessionManager(session_id=session_id, storage_dir=self.storage_dir)

# AFTER (CAST delegates to native, adds S3 option)
def get_manager(self, session_id):
    if self.bucket:
        return S3SessionManager(session_id=session_id, bucket=self.bucket, prefix=self.prefix)
    return FileSessionManager(session_id=session_id, storage_dir=self.storage_dir)
```

---

### 4. `cast.skills.SkillLoader` — DELETE ❌

**What CAST does:** Reads .md files from a directory, returns {name: instructions}.

**What Strands native has (v1.53.0):**
```python
from strands.vended_plugins.skills import AgentSkills, Skill

# Native: load skills from a directory of SKILL.md files
plugin = AgentSkills(skills=["./skills/"])  # reads all SKILL.md in dir
agent = Agent(plugins=[plugin])

# Native: programmatic skill
skill = Skill(name="youtuber", description="YouTube expert", instructions="...")
plugin = AgentSkills(skills=[skill])
```

**Why CAST's SkillLoader is redundant:**
- `AgentSkills` natively reads from filesystem paths (directories or individual skill dirs)
- It injects skill metadata into system prompt automatically (progressive disclosure)
- It provides a `skills` tool the agent calls to activate skills on-demand
- It persists activated skills in agent state for session continuity
- CAST's `write_skill_manifests()` converts .md → SKILL.md, but you could just write SKILL.md files directly

**Verdict:** DELETE SkillLoader entirely. Replace with a thin helper that converts flat .md files → SKILL.md directory structure (one-time conversion), then use native `AgentSkills`.

**Refactor:**
```python
# DELETE SkillLoader class
# KEEP only a helper function:
def md_to_skills(md_dir: str, output_dir: str) -> list[str]:
    """Convert flat .md files to SKILL.md directory structure for AgentSkills."""
    # youtuber.md → skills/youtuber/SKILL.md
    ...
    return created_dirs

# In factory.py, use native AgentSkills:
from strands.vended_plugins.skills import AgentSkills

plugin = AgentSkills(skills=["./skills/"])
agent = Agent(plugins=[plugin])
```

---

### 5. `cast.skills.PromptLoader` — KEEP ✅

**What CAST does:** Loads system prompts from .md files by name.

**What Strands native has:**
- `Agent(system_prompt="...")` — accepts a string or list of content blocks
- NO native "load prompt from file by name" feature
- The docs page for "Prompts" exists in the nav but returns 404 (not yet implemented)

**Verdict:** PromptLoader fills a genuine gap. No native equivalent. Keep as-is.

---

### 6. `cast.mcp` — SIMPLIFY ⚠️

**What CAST does:** MCPRegistry loads MCP servers from a JSON config file.

**What Strands native has:**
- `MCPClient(transport_callable, prefix)` — native MCP client
- Supports `streamablehttp_client` and `stdio_client` transports

**What CAST adds:**
- JSON config file format (like Windsurf/VSCode `mcp.json`)
- Auto-discovery of all servers from config
- Error isolation (one server failing doesn't block others)

**Verdict:** The JSON config pattern is useful and not native. But the implementation should use native `MCPClient` more directly. The current code already does this — it's just verbose.

**Minor refactor:** Simplify the transport builder, keep the JSON config pattern.

---

### 7. `cast.factory` — REFACTOR ⚠️ (most important)

**What CAST does:** AgentFactory creates agents with model, callbacks, sessions, skills, prompts, MCP.

**What Strands native has that CAST doesn't expose:**

| Native Feature | CAST exposes it? | Should expose? |
|----------------|------------------|----------------|
| `plugins` (AgentSkills, Steering, ContextOffloader, GoalLoop) | ❌ No | ✅ Yes — pass through |
| `hooks` (BeforeToolCall, AfterToolCall, BeforeModelCall, etc.) | ❌ No | ✅ Yes — pass through |
| `memory_manager` (MemoryManager with TestMemoryStore, BedrockKB) | ❌ No | ✅ Yes — huge feature |
| `conversation_manager` (SlidingWindow, Summarizing) | ❌ No | ✅ Yes — context management |
| `sandbox` (PosixShellSandbox, Docker) | ❌ No | ✅ Yes — for A2 agent |
| `storage` (LocalFile, S3, InMemory) | ❌ No | ✅ Yes — for sessions/state |
| `interventions` (Cedar auth, HITL) | ❌ No | ✅ Yes — for B1/B2 approval gates |
| `structured_output_model` (Pydantic) | ❌ No | ✅ Yes — for B1 JSON output |
| `retry_strategy` | ❌ No | ✅ Yes — Panne #5 backoff |
| `checkpointing` | ❌ No | ⚠️ Optional |
| `context_manager` ('auto', 'agentic') | ❌ No | ✅ Yes — Panne #6 sliding window |

**Verdict:** AgentFactory should pass through ALL native Agent params, not just the ones CAST wraps. This is the biggest refactor.

**Refactored AgentFactory.create_agent():**
```python
def create_agent(
    self,
    system_prompt: str = "",
    prompt_name: str | None = None,
    tools: list = None,
    session_id: str | None = None,
    include_mcp: bool = True,
    # NEW: native pass-through params
    plugins: list = None,
    hooks: list = None,
    memory_manager = None,
    conversation_manager = None,
    sandbox = None,
    storage = None,
    interventions = None,
    structured_output_model = None,
    retry_strategy = None,
    context_manager = None,
    **kwargs,
) -> Agent:
    ...
    return Agent(
        model=self.model,
        system_prompt=system_prompt,
        tools=all_tools or None,
        session_manager=session_manager,
        callback_handler=self.callback,
        # NEW: pass through native features
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
```

---

## New Features to ADD to CAST

Based on the native Strands v1.53.0 features, CAST should add these helpers:

### 1. `cast.conversation` — Context management helpers (Panne #6)

```python
from strands.agent.conversation_manager import SlidingWindowConversationManager

# Native: sliding window (keep last N messages)
SlidingWindowConversationManager(window_size=40)

# Native: summarizing (compress old messages into summary)
SummarizingConversationManager(summary_ratio=0.3, preserve_recent_messages=10)
```

**CAST helper:** A factory function that creates the right conversation manager based on a simple config.

### 2. `cast.memory` — Memory helpers

```python
from strands.memory import MemoryManager
from strands.vended_memory_stores.test_memory_store import TestMemoryStore

# Native: agent with long-term memory
store = TestMemoryStore(name="notes")
agent = Agent(memory_manager=MemoryManager(stores=[store]))
```

**CAST helper:** Pre-configured memory presets (local, S3, BedrockKB).

### 3. `cast.hooks` — Hook helpers (Panne #3 Circuit Breaker, #5 Backoff)

```python
from strands.hooks import HookProvider, HookCallback
from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent

# Native: hooks for tool call lifecycle
class CircuitBreakerHook(HookProvider):
    @property
    def registry(self):
        return {AfterToolCallEvent: self._on_after_tool}
```

**CAST helper:** Pre-built hook providers for Circuit Breaker, backoff, logging.

### 4. `cast.plugins` — Plugin helpers

```python
from strands.vended_plugins.skills import AgentSkills

# Native: skills plugin
plugin = AgentSkills(skills=["./skills/"])
agent = Agent(plugins=[plugin])
```

**CAST helper:** Auto-discover skills directory and create AgentSkills plugin.

---

## Final Action Plan (v0.2.0 — appliqué)

| Priority | Action | Module | Statut |
|----------|--------|--------|--------|
| 🔴 HIGH | **Refactor AgentFactory** to pass through native params (plugins, hooks, memory, conversation_manager, sandbox, storage, interventions, structured_output, retry, context_manager) | `factory.py` | ✅ Fait |
| 🔴 HIGH | **Delete SkillLoader** — replaced by native `AgentSkills` plugin | `skills.py` | ✅ Fait |
| 🟡 MED | **Add conversation helpers** — wrappers for SlidingWindow/SummarizingConversationManager | NEW `conversation.py` | ✅ Fait |
| 🟡 MED | **Add hooks helpers** — Circuit Breaker, backoff, logging hook providers | NEW `hooks.py` | ✅ Fait |
| 🟢 LOW | **Add memory helpers** — presets for TestMemoryStore, BedrockKB | NEW `memory.py` | ✅ Fait |
| 🟢 LOW | **Add plugin helpers** — auto-discover skills dir → AgentSkills | NEW `plugins.py` | ✅ Fait |
| ✅ KEEP | `models.py`, `callbacks.py`, `PromptLoader`, `MCPRegistry`, `cli.py` | — | ✅ |

---

## Analyse "Gros code vs 1-2 lignes" (v0.2.0 — post-refactor)

Critère : une feature justifie sa place dans CAST seulement si la recoder
à chaque agent prendrait beaucoup de lignes. Si c'est 1-2 lignes en natif
Strands, ça n'a pas sa place dans une lib.

| Feature | Lignes CAST | Verdict | Raison |
|---------|-------------|---------|--------|
| `OllamaCloudModel` | 15 | ⚠️ Borderline | `OllamaModel(host=..., ollama_client_args={"headers": {"Authorization": f"Bearer {key}"}})` — 2 lignes suffisent |
| `OpenAICompatModel` | 10 | ✅ KEEP | Override `format_request_message_content` pour reasoning_content — bug connu Strands, non-trivial |
| `from_env()` | 20 | ✅ KEEP | Auto-détection 3 providers avec priorité — utilisé à chaque agent |
| `AnimatedCallbackHandler` | 80 | ✅ KEEP | Thread-safe, ANSI, spinner, raisonnement — impossible en 2 lignes |
| `SessionManager.save()` | 25 | ✅ KEEP | Séquence delete→create session→agent→messages — pénible à recoder |
| `SessionManager.list()` | 5 | ❌ DELETE | `os.listdir()` en 1 ligne |
| `SessionManager.get_manager()` | 3 | ❌ DELETE | `FileSessionManager(session_id=..., storage_dir=...)` en 1 ligne |
| `PromptLoader` | 30 | ⚠️ Borderline | `Path("prompts/auditor.md").read_text()` — 3 lignes suffisent |
| `md_to_skill_dirs` | 15 | ❌ DELETE | 1 boucle `for` + `write_text` — faisable inline |
| `MCPRegistry` | 100 | ✅ KEEP | JSON parsing + 2 transports + error isolation + client lifecycle |
| `sliding_window()` | 3 | ❌ DELETE | `SlidingWindowConversationManager(window_size=40)` — 1 ligne native |
| `summarizing()` | 5 | ❌ DELETE | `SummarizingConversationManager(...)` — 1 ligne native |
| `no_conversation()` | 3 | ❌ DELETE | `NullConversationManager()` — 1 ligne native |
| `CircuitBreakerHook` | 40 | ⚠️ Borderline | Utile pour Panne #3 mais 40 lignes seulement |
| `ToolLogHook` | 15 | ❌ DELETE | `logger.info()` en 2 lignes |
| `local_memory()` | 8 | ❌ DELETE | `MemoryManager(stores=[TestMemoryStore(...)])` — 2 lignes natives |
| `skills_from_md_dir` | 20 | ⚠️ Borderline | Boucle + `Skill()` — faisable en 5 lignes |
| `skills_from_dir` | 3 | ❌ DELETE | `AgentSkills(skills=[dir])` — 1 ligne native |
| `AgentFactory` | 80 | ✅ KEEP | Orchestre model + callback + sessions + MCP + 10 pass-through natifs |
| `create_agent()` | 20 | ✅ KEEP | Convenience wrapper autour de AgentFactory |
| `cli.py` | 60 | ✅ KEEP | REPL avec /save /sessions /help — pas trivial |

### Recommandation de nettoyage (à appliquer plus tard si voulu)

**Garder (7 modules — gros code) :**
1. `factory.py` — AgentFactory + create_agent
2. `callbacks.py` — AnimatedCallbackHandler
3. `models.py` — OpenAICompatModel + from_env (OllamaCloudModel optionnel)
4. `sessions.py` — SessionManager.save() seulement
5. `mcp.py` — MCPRegistry
6. `cli.py` — REPL
7. `skills.py` — PromptLoader seulement

**Supprimer (trop léger vs natif) :**
- `conversation.py` (tout — 1 ligne native)
- `memory.py` (tout — 2 lignes natives)
- `plugins.py` (tout — 1 ligne native)
- `hooks.py` (CircuitBreakerHook borderline, ToolLogHook supprimer)
- `md_to_skill_dirs` dans skills.py
- `SessionManager.list()` et `get_manager()`

**Borderlines (à décider) :**
- `OllamaCloudModel` — 2 lignes en natif, mais pratique si Ollama Cloud utilisé souvent
- `PromptLoader` — 3 lignes en natif, mais pattern récurrent
- `CircuitBreakerHook` — 40 lignes, utile pour Panne #3 mais codable dans l'agent
- `skills_from_md_dir` — 5 lignes en natif, mais évite la conversion manuelle
