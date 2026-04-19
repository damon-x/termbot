"""
Response handler interface for Agent output.

Provides a protocol for handling agent responses,
allowing decoupling from specific output mechanisms (Web, CLI, etc).
"""
from typing import TYPE_CHECKING, Optional

from agent.react import ReactResult

if TYPE_CHECKING:
    from agent.core import Agent
    from infrastructure.terminal.pty_manager import PTYManager


class ResponseHandler:
    """
    Base class for handling agent responses.

    Implementations determine how responses are delivered:
    - Web: emit via socketio
    - CLI: print to console
    - System: log or forward to other systems
    """

    def on_response(self, result: ReactResult) -> None:
        """
        Handle a completed agent response.

        Args:
            result: The ReactResult from agent processing
        """
        raise NotImplementedError


class AgentReplyHandler(ResponseHandler):
    """
    Response handler that forwards results to another Agent.

    Used by Sub Agents to report completion back to their parent Agent.
    When a Sub Agent completes its task, this handler calls the parent
    Agent's submit() method to enqueue the result.

    If owned_pty is provided, it will be stopped after the response
    is forwarded (for cleanup of independent sub agent PTYs).
    """

    def __init__(
        self,
        parent_agent: 'Agent',
        task_id: Optional[str] = None,
        task_description: Optional[str] = None,
        owned_pty: Optional['PTYManager'] = None
    ) -> None:
        """
        Initialize the handler.

        Args:
            parent_agent: The parent Agent to forward results to
            task_id: Optional task identifier for tracking
            task_description: Optional description of the original task
            owned_pty: Optional PTY owned by this sub agent (will be stopped on completion)
        """
        self.parent_agent = parent_agent
        self.task_id = task_id
        self.task_description = task_description
        self.owned_pty = owned_pty

    def on_response(self, result: ReactResult) -> None:
        """
        Forward the result to the parent agent and clean up resources.

        Args:
            result: The ReactResult from sub agent processing
        """
        from infrastructure.logging import get_logger
        logger = get_logger("agent.reply_handler")

        # Build message for parent agent
        message = self._format_result_message(result)

        logger.info(
            "Sub agent completed, forwarding to parent",
            task_id=self.task_id,
            success=result.success,
            status=result.status
        )

        # Submit to parent agent's queue
        self.parent_agent.submit(message)

        # Clean up owned PTY if present
        if self.owned_pty:
            try:
                self.owned_pty.stop()
                logger.info("Stopped sub agent PTY", task_id=self.task_id)
            except Exception as e:
                logger.error("Failed to stop sub agent PTY", error=str(e))

    def _format_result_message(self, result: ReactResult) -> str:
        """
        Format the result as a message for the parent agent.

        Args:
            result: The ReactResult

        Returns:
            Formatted message string
        """
        parts = []

        # Task identification
        if self.task_id:
            parts.append(f"[子任务 #{self.task_id}]")
        if self.task_description:
            parts.append(f"任务: {self.task_description}")

        # Status
        if result.success:
            parts.append("状态: 完成")
        else:
            parts.append(f"状态: 失败 ({result.error or '未知错误'})")

        # Result content
        if result.response:
            parts.append(f"结果:\n{result.response}")

        return "\n".join(parts)
