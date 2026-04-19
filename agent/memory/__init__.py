"""
Agent memory module.

Exports:
- Unified memory system (models, long_term_memory)

Phase 5: Legacy components removed
"""
from agent.memory.models import MemoryItem, MemoryManager, memory_manager
from agent.memory.long_term_memory import (
    LongTermMemory,
    MemoryResult,
    SetResult,
    get_long_term_memory,
)


__all__ = [
    # Unified system
    "MemoryItem",
    "MemoryManager",
    "memory_manager",
    "LongTermMemory",
    "MemoryResult",
    "SetResult",
    "get_long_term_memory",
]
