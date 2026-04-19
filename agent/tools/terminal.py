"""
Terminal tool implementation using PTYManager.

Provides true terminal command execution with output capture
and proper locking coordination with web sessions.
"""
import platform
import re
import time
from typing import Any, Dict

# Prompt detection: shell ready for input ($ # > % or : at end of output)
_PROMPT_RE = re.compile(r'[$#>%]\s*$|:\s*$')
# ANSI escape sequence strip (for clean prompt matching)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\r')
# Polling parameters
_POLL_INTERVAL = 0.05    # 50ms poll cycle
_IDLE_THRESHOLD = 0.8    # 800ms no-new-output → consider done
_WAIT_TIMEOUT = 30.0     # max wait per command

from agent.tools.base import Tool, ToolSchema, ToolParameter, ToolParameterType
from infrastructure.terminal.pty_manager import PTYManager


class TerminalTool(Tool):
    """
    Terminal command execution tool.

    Uses PTYManager to execute commands with proper locking.
    Can preempt web sessions when needed.
    """

    def __init__(self, pty_manager: PTYManager, instance_id: str = "main"):
        """
        Initialize terminal tool.

        Args:
            pty_manager: PTY Manager instance
            instance_id: Runtime instance identifier for PTY locking
        """
        self.pty_manager = pty_manager
        self.instance_id = instance_id

        # Output buffer for capturing command results
        self._output_buffer: list[str] = []
        self._collecting = False

        # Register listener for output capture
        pty_manager.register_listener(self._on_terminal_output)

    def _on_terminal_output(self, data: str) -> None:
        """
        Handle PTY output.

        When collecting, store output in buffer.
        Always pass through for other listeners.
        """
        if self._collecting:
            self._output_buffer.append(data)

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="exec_terminal_cmd",
            description=(
                "Execute a command in the terminal and return the output. "
                "Can open URLs in browser (e.g., 'open https://example.com'), "
                "launch applications, manage files, or run any shell command. "
                "Also accepts input text like confirmations (y), quit (q), or passwords.\n\n"
                "CRITICAL: Commands are executed in the current terminal/SSH session. "
                "Before using platform-specific commands, check the current system type:\n"
                "- Run 'uname' or 'cat /etc/os-release' to identify the OS\n"
                "- Run 'which <command>' to check if a command exists\n\n"
                "Platform-specific commands:\n"
                "- Memory info: 'free -h' (Linux), 'vm_stat' (macOS), 'system_profiler SPHardwareDataType' (macOS GUI)\n"
                "- CPU count: 'nproc' (Linux), 'sysctl -n hw.ncpu' (macOS)\n"
                "- Disk info: 'df -h' (both), 'diskutil list' (macOS)\n\n"
                "If a command fails with 'command not found', try alternatives or check the OS type first."
            ),
            parameters=[
                ToolParameter(
                    name="cmd",
                    type=ToolParameterType.STRING,
                    description=(
                        "Command to execute. Examples: "
                        "'ls -la', 'df -h', 'free -h', 'docker ps', "
                        "'y' for confirmation, 'q' to quit"
                    ),
                    required=True
                )
            ]
        )

    def execute(self, cmd: str) -> str:
        """
        Execute terminal command with automatic fallback for cross-platform compatibility.

        Args:
            cmd: Command to execute

        Returns:
            Command output or error message
        """
        if not self.pty_manager.is_running():
            return "Error: PTY is not running"

        # 禁用自动 fallback，避免本地系统检测干扰远程执行
        # 直接执行用户提供的命令，让 Agent 自己判断系统类型
        cmd_to_execute = cmd

        # Start collecting output
        self._collecting = True
        self._output_buffer = []

        # Execute command using PTYManager's agent write method
        # This handles locking and preemption automatically
        result = self.pty_manager.write_agent(cmd_to_execute, self.instance_id)

        if not result.success:
            self._collecting = False
            return f"Failed to execute command: {result.message}"

        # Wait for command: prompt detection (high confidence) + idle fallback
        _start = time.time()
        _last_len = 0
        _last_change = time.time()
        while time.time() - _start < _WAIT_TIMEOUT:
            time.sleep(_POLL_INTERVAL)
            _cur_len = len(self._output_buffer)
            if _cur_len != _last_len:
                _last_len = _cur_len
                _last_change = time.time()
                _raw_tail = ''.join(self._output_buffer)[-300:]
                _clean_tail = _ANSI_RE.sub('', _raw_tail)
                if _PROMPT_RE.search(_clean_tail):
                    break
            elif time.time() - _last_change > _IDLE_THRESHOLD:
                break

        # Stop collecting and get output
        self._collecting = False
        output = "".join(self._output_buffer)

        # Clean up output (remove trailing whitespace)
        output = output.strip()

        return output if output else "(command executed with no output)"


class TerminalBufferTool(Tool):
    """
    Terminal buffer content retrieval tool.
    
    Returns the terminal output buffer content (recent terminal history).
    All ANSI escape sequences are stripped for cleaner text.
    """
    
    def __init__(self, pty_manager: PTYManager):
        """
        Initialize terminal buffer tool.
        
        Args:
            pty_manager: PTY Manager instance with buffer
        """
        self.pty_manager = pty_manager
    
    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name="get_terminal_buffer",
            description=(
                "Get the terminal buffer content (recent output history). "
                "Use this when you need to:\n"
                "- See what the user has done in the terminal\n"
                "- Check if a long-running command has produced more output\n"
                "- Get context about the current terminal state\n"
                "- Review previous command outputs\n\n"
                "Returns the recent terminal output (up to ~20KB, ANSI sequences stripped). "
                "Note: This includes ALL terminal output, including your previous command results."
            ),
            parameters=[
                ToolParameter(
                    name="max_chars",
                    type=ToolParameterType.INTEGER,
                    description=(
                        "Maximum characters to return. "
                        "Default is 10000. Use larger values (up to 20000) if you need more context."
                    ),
                    required=False
                )
            ]
        )
    
    def execute(self, max_chars: int = 10000) -> str:
        """
        Get terminal buffer content.
        
        Args:
            max_chars: Maximum characters to return
            
        Returns:
            Terminal buffer content
        """
        if not self.pty_manager.is_running():
            return "Error: PTY is not running"
        
        content = self.pty_manager.get_buffer_content(max_chars=max_chars)
        
        if not content:
            return "(terminal buffer is empty)"
        
        return content
