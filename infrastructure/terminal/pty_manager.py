"""
PTY Manager - Terminal process management with locking mechanism.

Implements session-based locking and priority-based preemption for
coordinating between Web user input and Agent commands.
"""
import os
import pty
import re
import select
import threading
import time
import enum
from collections import deque
from typing import Callable, List, Optional, Dict, Any
from dataclasses import dataclass, field

from infrastructure.logging import get_logger, EventType

logger = get_logger("pty.manager")


# ANSI escape sequence pattern for stripping
ANSI_ESCAPE_PATTERN = re.compile(
    r'\x1b\[[0-9;]*[a-zA-Z]'  # CSI sequences: \x1b[...m, \x1b[...K, etc.
    r'|\x1b\].*?\x07'         # OSC sequences: \x1b]...\x07
    r'|\x1b[()][AB012]'       # Character set: \x1b(A, \x1b)B, etc.
    r'|\x1b[=>]'              # Keypad mode: \x1b=, \x1b>
    r'|\x1b[78]'              # Save/restore cursor: \x1b7, \x1b8
    r'|\r'                    # Carriage return (keep newlines)
)


class TerminalBuffer:
    """
    Terminal output buffer with ANSI stripping and size limits.
    
    Maintains a sliding window of terminal output content.
    All ANSI escape sequences are stripped for cleaner text.
    """
    
    DEFAULT_MAX_CHARS = 20000
    
    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS):
        """
        Initialize terminal buffer.
        
        Args:
            max_chars: Maximum characters to store (sliding window)
        """
        self._max_chars = max_chars
        self._buffer: deque = deque()
        self._total_chars = 0
        self._lock = threading.Lock()
    
    def append(self, text: str) -> None:
        """
        Append text to buffer, stripping ANSI sequences.
        
        Args:
            text: Raw terminal output
        """
        # Strip ANSI escape sequences
        clean_text = ANSI_ESCAPE_PATTERN.sub('', text)
        
        if not clean_text:
            return
        
        with self._lock:
            self._buffer.append(clean_text)
            self._total_chars += len(clean_text)
            
            # Enforce size limit using sliding window
            while self._total_chars > self._max_chars and self._buffer:
                removed = self._buffer.popleft()
                self._total_chars -= len(removed)
    
    def get_content(self, max_chars: Optional[int] = None) -> str:
        """
        Get buffer content.
        
        Args:
            max_chars: Optional limit on characters to return
            
        Returns:
            Buffer content as string
        """
        with self._lock:
            content = ''.join(self._buffer)
            
            if max_chars and len(content) > max_chars:
                # Return last max_chars characters
                content = content[-max_chars:]
            
            return content
    
    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()
            self._total_chars = 0
    
    def get_size(self) -> int:
        """Get current buffer size in characters."""
        with self._lock:
            return self._total_chars


class LockPriority(enum.IntEnum):
    """Lock priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    AGENT = HIGH  # Agent commands have high priority
    WEB = NORMAL  # Web user input has normal priority


@dataclass
class LockResult:
    """Result of lock operations."""
    success: bool
    message: str = ""
    preempted: bool = False
    owner: Optional[str] = None


@dataclass
class SessionInfo:
    """Information about a lock session."""
    owner: str
    priority: LockPriority
    acquire_time: float
    last_activity: float
    timeout: float = 2.0  # Session timeout in seconds

    def is_expired(self) -> bool:
        """Check if session has expired due to inactivity."""
        return time.time() - self.last_activity > self.timeout

    def touch(self):
        """Update last activity time."""
        self.last_activity = time.time()


class PTYInputLock:
    """
    PTY Input Lock with session-based locking and priority preemption.

    Features:
    - Session-based locking for continuous input (e.g., Web typing)
    - Priority-based preemption (Agent can preempt Web)
    - Automatic timeout on session inactivity
    - Preemption notifications
    """

    def __init__(self, default_timeout: float = 30.0):
        """
        Initialize the lock.

        Args:
            default_timeout: Default timeout for acquire operations
        """
        self._session: Optional[SessionInfo] = None
        self._default_timeout = default_timeout
        self._lock = threading.Lock()
        self._preemption_callbacks: List[Callable[[str, str], None]] = []

    def register_preemption_callback(self, callback: Callable[[str, str], None]) -> None:
        """
        Register a callback to be called when preemption happens.

        Args:
            callback: Function called with (old_owner, new_owner)
        """
        self._preemption_callbacks.append(callback)

    def acquire(
        self,
        owner: str,
        priority: LockPriority = LockPriority.NORMAL,
        timeout: Optional[float] = None,
        session_timeout: float = 2.0
    ) -> LockResult:
        """
        Acquire the lock.

        Args:
            owner: Unique identifier for the lock owner
            priority: Priority level for this acquisition
            timeout: Max time to wait for lock (None = use default)
            session_timeout: Session inactivity timeout

        Returns:
            LockResult indicating success or failure
        """
        timeout = timeout or self._default_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self._lock:
                # Case 1: No one holds the lock
                if self._session is None:
                    self._session = SessionInfo(
                        owner=owner,
                        priority=priority,
                        acquire_time=time.time(),
                        last_activity=time.time(),
                        timeout=session_timeout
                    )
                    return LockResult(
                        success=True,
                        message=f"Lock acquired by {owner}",
                        owner=owner
                    )

                # Case 2: Same owner acquiring again (session renewal)
                if self._session.owner == owner:
                    self._session.touch()
                    return LockResult(
                        success=True,
                        message=f"Lock renewed by {owner}",
                        owner=owner
                    )

                # Case 3: Current session expired
                if self._session.is_expired():
                    old_owner = self._session.owner
                    self._session = SessionInfo(
                        owner=owner,
                        priority=priority,
                        acquire_time=time.time(),
                        last_activity=time.time(),
                        timeout=session_timeout
                    )
                    return LockResult(
                        success=True,
                        message=f"Lock acquired after {old_owner} timeout",
                        owner=owner
                    )

                # Case 4: Preemption - higher priority can take lock
                if priority > self._session.priority:
                    old_owner = self._session.owner
                    self._session = SessionInfo(
                        owner=owner,
                        priority=priority,
                        acquire_time=time.time(),
                        last_activity=time.time(),
                        timeout=session_timeout
                    )

                    # Notify preemption callbacks
                    for callback in self._preemption_callbacks:
                        try:
                            callback(old_owner, owner)
                        except Exception:
                            pass

                    return LockResult(
                        success=True,
                        message=f"Lock preempted from {old_owner}",
                        preempted=True,
                        owner=owner
                    )

            # Lock held by someone else, wait a bit
            time.sleep(0.05)

        # Timeout
        current_owner = self._session.owner if self._session else "none"
        return LockResult(
            success=False,
            message=f"Lock acquisition timeout (held by {current_owner})",
            owner=current_owner
        )

    def release(self, owner: str) -> LockResult:
        """
        Release the lock.

        Args:
            owner: Owner trying to release

        Returns:
            LockResult indicating success or failure
        """
        with self._lock:
            if self._session is None:
                return LockResult(
                    success=False,
                    message="Lock is not held"
                )

            if self._session.owner != owner:
                return LockResult(
                    success=False,
                    message=f"Lock not owned by {owner} (owned by {self._session.owner})"
                )

            released_owner = self._session.owner
            self._session = None

            return LockResult(
                success=True,
                message=f"Lock released by {released_owner}"
            )

    def renew_session(self, owner: str) -> LockResult:
        """
        Renew a session (update last activity time).

        Args:
            owner: Session owner

        Returns:
            LockResult indicating success or failure
        """
        with self._lock:
            if self._session is None or self._session.owner != owner:
                return LockResult(
                    success=False,
                    message="No active session for this owner"
                )

            self._session.touch()
            return LockResult(
                success=True,
                message=f"Session renewed by {owner}"
            )

    def is_locked(self) -> bool:
        """Check if lock is currently held."""
        with self._lock:
            return self._session is not None

    def get_owner(self) -> Optional[str]:
        """Get current lock owner."""
        with self._lock:
            return self._session.owner if self._session else None

    def get_session_info(self) -> Optional[SessionInfo]:
        """Get current session info."""
        with self._lock:
            return self._session

    def get_lock_status(self) -> Dict[str, Any]:
        """
        Get current lock status.

        Returns:
            Dict with lock status information
        """
        with self._lock:
            if self._session is None:
                return {
                    "locked": False,
                    "owner": None,
                    "priority": None
                }

            return {
                "locked": True,
                "owner": self._session.owner,
                "priority": self._session.priority.name,
                "idle_time": time.time() - self._session.last_activity,
                "is_web": self._session.priority == LockPriority.WEB,
                "is_agent": self._session.priority == LockPriority.AGENT
            }

    @property
    def is_web_locked(self) -> bool:
        """Check if locked by a web session."""
        with self._lock:
            return (
                self._session is not None and
                self._session.priority == LockPriority.WEB
            )

    @property
    def is_agent_locked(self) -> bool:
        """Check if locked by agent."""
        with self._lock:
            return (
                self._session is not None and
                self._session.priority == LockPriority.AGENT
            )


class PTYManager:
    """
    Manages PTY (pseudo-terminal) with multi-listener support and coordinated input.

    Features:
    - PTY process lifecycle management
    - Input locking with session support and preemption
    - Multiple output listeners (Web, Agent, etc.)
    - Listener isolation (one listener's error doesn't affect others)
    - Terminal output buffer with ANSI stripping
    """

    def __init__(
        self,
        shell: str = "/bin/bash",
        cols: int = 80,
        rows: int = 24,
        session_timeout: float = 2.0,
        max_buffer_chars: int = TerminalBuffer.DEFAULT_MAX_CHARS
    ):
        """
        Initialize PTY Manager.

        Args:
            shell: Shell program to run
            cols: Terminal width
            rows: Terminal height
            session_timeout: Web session inactivity timeout in seconds
            max_buffer_chars: Maximum characters in terminal buffer
        """
        self.shell = shell
        self.cols = cols
        self.rows = rows
        self._session_timeout = session_timeout

        # PTY state
        self.pid: Optional[int] = None
        self.fd: Optional[int] = None
        self._running = False

        # Input lock
        self._input_lock = PTYInputLock()

        # Output listeners
        self._listeners: List[Callable[[str], None]] = []
        self._read_thread: Optional[threading.Thread] = None

        # Terminal buffer (stores all output)
        self._buffer = TerminalBuffer(max_chars=max_buffer_chars)

        # Register preemption callback for notifications
        self._input_lock.register_preemption_callback(self._on_preemption)

    def _on_preemption(self, old_owner: str, new_owner: str) -> None:
        """
        Called when lock is preempted.

        Args:
            old_owner: Previous lock owner
            new_owner: New lock owner
        """
        # Send notification through listeners
        notification = f"\r\n[Lock preempted: {old_owner} -> {new_owner}]\r\n"
        self._notify_listeners(notification)

    def start(self) -> None:
        """Start the PTY process."""
        if self._running:
            return

        # Fork PTY
        self.pid, self.fd = pty.fork()

        if self.pid == 0:
            # Child process - run shell
            os.execv(self.shell, [self.shell])

        # Parent process
        self._running = True
        self._set_terminal_size(self.cols, self.rows)
        self._start_read_thread()

    def _start_read_thread(self) -> None:
        """Start the background read thread."""
        self._read_thread = threading.Thread(
            target=self._read_loop,
            daemon=True
        )
        self._read_thread.start()

    def _read_loop(self) -> None:
        """
        Read loop - continuously read from PTY and notify listeners.

        Runs in a background thread.
        """
        while self._running:
            try:
                # Wait for data with timeout
                r, _, _ = select.select([self.fd], [], [], 0.1)

                if r:
                    # Data available
                    data = os.read(self.fd, 1024)
                    if not data:
                        # EOF - child process exited
                        break

                    # Decode and notify listeners
                    try:
                        text = data.decode('utf-8', errors='replace')
                        # Append to terminal buffer (strips ANSI)
                        self._buffer.append(text)
                        # Notify listeners (raw text with ANSI)
                        self._notify_listeners(text)
                    except Exception as e:
                        logger.warning("PTY decode error", error=str(e))

            except OSError:
                # PTY closed
                break

    def register_listener(self, callback: Callable[[str], None]) -> None:
        """
        Register an output listener.

        Args:
            callback: Function to call with PTY output data
        """
        self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[str], None]) -> None:
        """
        Unregister an output listener.

        Args:
            callback: Listener to remove
        """
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, data: str) -> None:
        """
        Notify all listeners of PTY output.

        Args:
            data: Output data from PTY
        """
        for listener in self._listeners:
            try:
                listener(data)
            except Exception as e:
                # Isolate listener errors
                logger.warning("PTY listener error", error=str(e))

    # Web session methods

    def start_web_session(self, sid: str) -> LockResult:
        """
        Start a web typing session (acquires lock).

        Args:
            sid: Session ID (socketio sid)

        Returns:
            LockResult
        """
        owner = f"web_{sid}"
        return self._input_lock.acquire(
            owner=owner,
            priority=LockPriority.WEB,
            timeout=5.0,
            session_timeout=self._session_timeout
        )

    def end_web_session(self, sid: str) -> LockResult:
        """
        End a web typing session (releases lock).

        Args:
            sid: Session ID

        Returns:
            LockResult
        """
        owner = f"web_{sid}"
        return self._input_lock.release(owner)

    def renew_web_session(self, sid: str) -> LockResult:
        """
        Renew web session (update activity time).

        Args:
            sid: Session ID

        Returns:
            LockResult
        """
        owner = f"web_{sid}"
        return self._input_lock.renew_session(owner)

    def write_web(self, data: str, sid: str) -> LockResult:
        """
        Write data to PTY from web session.

        This method:
        1. Auto-starts session if not active
        2. Renews session activity
        3. Writes data directly (no additional locking needed)

        Args:
            data: Data to write
            sid: Session ID

        Returns:
            LockResult
        """
        # Auto-start session if needed
        if not self._input_lock.is_locked:
            result = self.start_web_session(sid)
            if not result.success:
                return result
        elif self._input_lock.get_owner() == f"web_{sid}":
            # Renew existing session
            self.renew_web_session(sid)

        # Write data
        return self._write_direct(data)

    # Agent methods

    def write_agent(self, command: str, agent_id: str) -> LockResult:
        """
        Write a command to PTY from Agent.

        This method:
        1. Acquires lock with high priority (can preempt Web)
        2. Writes command + newline
        3. Waits for output
        4. Releases lock

        Args:
            command: Command to execute
            agent_id: Unique agent identifier

        Returns:
            LockResult
        """
        owner = f"agent_{agent_id}"

        # DEBUG 级别：PTY 命令详情（不显示）
        # logger.log_event(EventType.PTY_COMMAND, {
        #     "command": command[:400] + "..." if len(command) > 400 else command,
        #     "owner": owner,
        # })

        # Try to acquire lock (can preempt web sessions)
        result = self._input_lock.acquire(
            owner=owner,
            priority=LockPriority.AGENT,
            timeout=30.0,
            session_timeout=0  # Agent doesn't use session timeout
        )

        if not result.success:
            logger.warning("PTY lock acquisition failed", owner=owner, message=result.message)
            return result

        # DEBUG 级别：锁获取详情（不显示）
        # logger.log_event(EventType.PTY_LOCK_ACQUIRED, {
        #     "owner": owner,
        #     "preempted": result.preempted,
        # })

        try:
            # Write command
            self._write_direct(command + "\n")

            # Give command time to execute
            time.sleep(0.5)

            return LockResult(
                success=True,
                message=f"Command executed: {command}",
                owner=owner
            )

        finally:
            # Always release lock
            self._input_lock.release(owner)
            # DEBUG 级别：锁释放详情（不显示）
            # logger.log_event(EventType.PTY_LOCK_RELEASED, {
            #     "owner": owner,
            # })

    # Core write method

    def _write_direct(self, data: str) -> LockResult:
        """
        Write data directly to PTY (assumes lock is already held).

        Args:
            data: Data to write

        Returns:
            LockResult
        """
        if self.fd is None:
            return LockResult(
                success=False,
                message="PTY not started"
            )

        try:
            os.write(self.fd, data.encode('utf-8'))
            return LockResult(success=True, message="Write successful")
        except OSError as e:
            return LockResult(
                success=False,
                message=f"Write error: {e}"
            )

    # Utility methods

    def resize(self, cols: int, rows: int) -> None:
        """
        Resize terminal window.

        Args:
            cols: Number of columns
            rows: Number of rows
        """
        if self.fd is None:
            return

        import fcntl
        import struct
        import termios

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

        self.cols = cols
        self.rows = rows

    def _set_terminal_size(self, cols: int, rows: int) -> None:
        """Set initial terminal size."""
        self.resize(cols, rows)

    def stop(self) -> None:
        """Stop the PTY process."""
        self._running = False

        if self.fd:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

        if self.pid:
            try:
                os.kill(self.pid, 9)  # SIGKILL
            except OSError:
                pass
            self.pid = None

        # Clear listeners
        self._listeners.clear()

    # Status methods

    def is_running(self) -> bool:
        """Check if PTY is running."""
        return self._running

    def get_lock_status(self) -> Dict[str, Any]:
        """
        Get current lock status.

        Returns:
            Dict with lock status information
        """
        session = self._input_lock.get_session_info()

        if session is None:
            return {
                "locked": False,
                "owner": None,
                "priority": None
            }

        return {
            "locked": True,
            "owner": session.owner,
            "priority": session.priority.name,
            "idle_time": time.time() - session.last_activity,
            "is_web": session.priority == LockPriority.WEB,
            "is_agent": session.priority == LockPriority.AGENT
        }

    def get_buffer_content(self, max_chars: Optional[int] = None) -> str:
        """
        Get terminal buffer content.

        Args:
            max_chars: Optional limit on characters to return

        Returns:
            Terminal output buffer content (ANSI stripped)
        """
        return self._buffer.get_content(max_chars)

    def clear_buffer(self) -> None:
        """Clear the terminal buffer."""
        self._buffer.clear()

    def get_buffer_size(self) -> int:
        """Get current buffer size in characters."""
        return self._buffer.get_size()
