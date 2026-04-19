"""
PTY Terminal management module.

Provides PTY process management with session-based locking
and priority-based preemption for coordinating between Web user input
and Agent commands.
"""
from infrastructure.terminal.pty_manager import (
    LockPriority,
    LockResult,
    PTYInputLock,
    PTYManager,
    SessionInfo,
)

__all__ = [
    "PTYManager",
    "PTYInputLock",
    "LockPriority",
    "LockResult",
    "SessionInfo",
]
