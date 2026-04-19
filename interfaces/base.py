"""
Base interface handler module.

Provides abstract base class for interface handlers (Web, CLI, etc.)
that interact with the Agent core.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from agent.core import Agent


class BaseHandler(ABC):
    """
    Abstract base class for interface handlers.

    Interface handlers handle the interaction layer between users
    and the Agent core, managing message flow and callbacks.
    """

    def __init__(self, agent: Agent) -> None:
        """
        Initialize the handler with an agent instance.

        Args:
            agent: Agent instance to interact with
        """
        self.agent = agent
        self._is_running = False
        self._response_callbacks: List[Callable[[str], None]] = []
        self._error_callbacks: List[Callable[[Exception], None]] = []

    @abstractmethod
    def start(self) -> None:
        """Start the interaction handler."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the interaction handler."""
        pass

    @abstractmethod
    def send_message(self, message: str) -> str:
        """
        Send a message to the agent and get response.

        Args:
            message: User's message

        Returns:
            Agent's response
        """
        pass

    def send_message_async(self, message: str, callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Send a message asynchronously with optional callback.

        Args:
            message: User's message
            callback: Optional callback for the response
        """
        if callback:
            self._response_callbacks.append(callback)

        # Default implementation calls sync version
        # Subclasses can override for true async behavior
        try:
            response = self.send_message(message)
            if callback:
                callback(response)
        except Exception as e:
            self._handle_error(e)

    def on_agent_response(self, response: str) -> None:
        """
        Callback called when agent responds.

        Args:
            response: Agent's response
        """
        for callback in self._response_callbacks:
            try:
                callback(response)
            except Exception:
                pass  # Don't let one bad callback break others

    def on_agent_error(self, error: Exception) -> None:
        """
        Callback called when an error occurs.

        Args:
            error: Exception that occurred
        """
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception:
                pass

    def register_response_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback for agent responses.

        Args:
            callback: Function to call with response
        """
        self._response_callbacks.append(callback)

    def register_error_callback(self, callback: Callable[[Exception], None]) -> None:
        """
        Register a callback for errors.

        Args:
            callback: Function to call with error
        """
        self._error_callbacks.append(callback)

    def clear_callbacks(self) -> None:
        """Clear all registered callbacks."""
        self._response_callbacks.clear()
        self._error_callbacks.clear()

    def is_running(self) -> bool:
        """
        Check if the handler is running.

        Returns:
            True if running
        """
        return self._is_running

    def _handle_error(self, error: Exception) -> None:
        """
        Internal error handling.

        Args:
            error: Exception that occurred
        """
        self.on_agent_error(error)

    def get_agent(self) -> Agent:
        """
        Get the associated agent instance.

        Returns:
            The Agent instance
        """
        return self.agent

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history.

        Returns:
            List of message dicts
        """
        return self.agent.get_conversation_history()

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.agent.reset_conversation()

    def get_available_tools(self) -> List[str]:
        """
        Get list of available tools.

        Returns:
            List of tool names
        """
        return self.agent.get_available_tools()

    def is_waiting_for_user(self) -> bool:
        """
        Check if agent is waiting for user input.

        Returns:
            True if waiting
        """
        return self.agent.is_paused()

    def provide_user_answer(self, answer: str) -> None:
        """
        Provide user answer when agent is waiting.

        Args:
            answer: User's answer
        """
        self.agent.provide_user_answer(answer)

    def export_checkpoint(self) -> Dict[str, Any]:
        """
        Export current state as checkpoint.

        Returns:
            Checkpoint data
        """
        return self.agent.export_checkpoint()

    def load_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """
        Load state from checkpoint.

        Args:
            checkpoint: Checkpoint data
        """
        self.agent.load_checkpoint(checkpoint)
