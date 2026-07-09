"""Memory helpers — presets for native Strands MemoryManager.

Native Strands v1.53.0 provides:
  - MemoryManager(stores=[...], search_tool_config=True, add_tool_config=False)
  - TestMemoryStore (local disk, zero setup)
  - BedrockKnowledgeBaseStore (managed AWS)

These helpers create pre-configured memory managers from a simple config.
"""

from strands.memory import MemoryManager
from strands.memory.types import MemoryManagerConfig


def local_memory(name: str = "default", add_tool: bool = True) -> MemoryManager:
    """Create a local disk-backed memory manager (zero setup).

    Persists to ~/.strands/memory/<name>.json by default.
    The agent can recall and store memories across sessions.

    Args:
        name: Memory store name (becomes the file name).
        add_tool: Give the agent an `add_memory` tool to save memories.
    """
    from strands.vended_memory_stores.test_memory_store import TestMemoryStore, TestMemoryStoreConfig

    store = TestMemoryStore(store_config=TestMemoryStoreConfig(name=name))
    return MemoryManager(stores=[store], add_tool_config=add_tool)
