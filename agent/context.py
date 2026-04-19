"""
Context module for managing agent execution context.

Provides thread-local context for agent operations including
message history, state management, and task tracking.
This is a decoupled version that doesn't depend on any interface layer.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Message:
    """
    Message in conversation history.

    Attributes:
        role: Message role (user/assistant/system/tool)
        content: Message content
        metadata: Optional metadata for the message
    """
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class Context:
    """
    Agent execution context.

    Manages conversation state, message history, and task tracking
    without dependencies on any interface layer (web/cli).
    """

    def __init__(self) -> None:
        """Initialize a new context instance."""
        # Message history
        self._messages: List[Message] = []

        # User input
        self._user_input: str = ""

        # State management
        self._state: Dict[str, Any] = {}

        # Status tracking
        self._status: str = "running"  # running/success/failed/interrupted

        # Task management
        self._tasks: List[Dict[str, Any]] = []

        # Chat status
        self._chat_status: str = "running"  # running/pause

        # Flags
        self._waiting_user_answer: bool = False
        self._user_answer: str = ""
        self._need_terminal: bool = False

        # Terminal content cache
        self._terminal_content: str = ""

        # Optional callback invoked on every add_message()
        self._message_callback: Optional[Callable[["Message"], None]] = None

        # Current request ID (set at the start of each ReAct run)
        self._current_request_id: Optional[str] = None

    def set_request_id(self, request_id: Optional[str]) -> None:
        """Set the current request ID, injected into every subsequent message's metadata."""
        self._current_request_id = request_id

    def set_message_callback(self, callback: Callable[["Message"], None]) -> None:
        """
        Register a callback to be called whenever a message is added.

        Args:
            callback: Function that receives a Message instance
        """
        self._message_callback = callback

    # Message management

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to conversation history.

        Args:
            role: Message role (user/assistant/system/tool)
            content: Message content
            metadata: Optional metadata for the message
        """
        meta = metadata or {}
        if self._current_request_id and 'request_id' not in meta:
            meta['request_id'] = self._current_request_id
        message = Message(role=role, content=content, metadata=meta)
        self._messages.append(message)
        if self._message_callback:
            self._message_callback(message)

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get messages in LLM-compatible format.

        Returns:
            List of message dicts with 'role' and 'content' keys.
            For 'tool' role messages, includes 'tool_call_id' if available.
            For 'assistant' role messages, includes 'tool_calls' if available.

        Note: OpenAI API requires content to be a string (not None).
        For assistant messages with tool_calls, content can be an empty string.
        """
        messages = []
        for msg in self._messages:
            message_dict: Dict[str, Any] = {
                "role": msg.role,
                # Ensure content is always a string (never None)
                "content": msg.content if msg.content is not None else ""
            }

            # Add tool_call_id for tool role messages
            if msg.role == "tool" and msg.metadata.get("tool_call_id"):
                message_dict["tool_call_id"] = msg.metadata["tool_call_id"]

            # Add tool_calls for assistant role messages
            if msg.role == "assistant" and msg.metadata.get("tool_calls"):
                message_dict["tool_calls"] = msg.metadata["tool_calls"]

            messages.append(message_dict)
        return messages

    def get_full_messages(self) -> List[Message]:
        """
        Get full message objects with metadata.

        Returns:
            List of Message objects
        """
        return self._messages.copy()

    def clear_messages(self) -> None:
        """Clear all messages from history."""
        self._messages.clear()

    @property
    def message_count(self) -> int:
        """Get the number of messages in history."""
        return len(self._messages)

    # User input management

    def set_user_input(self, user_input: str) -> None:
        """
        Set the current user input.

        Args:
            user_input: User input text
        """
        self._user_input = user_input

    def get_user_input(self) -> str:
        """
        Get the current user input.

        Returns:
            Current user input text
        """
        return self._user_input

    # State management

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a state value.

        Args:
            key: State key
            value: State value
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a state value.

        Args:
            key: State key
            default: Default value if key doesn't exist

        Returns:
            State value or default
        """
        return self._state.get(key, default)

    def clear_state(self) -> None:
        """Clear all state values."""
        self._state.clear()

    # Status management

    def set_status(self, status: str) -> None:
        """
        Set the execution status.

        Args:
            status: Status value (running/success/failed/interrupted)
        """
        self._status = status

    def get_status(self) -> str:
        """
        Get the current status.

        Returns:
            Current status
        """
        return self._status

    def is_running(self) -> bool:
        """Check if status is running."""
        return self._status == "running"

    def is_complete(self) -> bool:
        """Check if status is success."""
        return self._status == "success"

    def is_failed(self) -> bool:
        """Check if status is failed."""
        return self._status == "failed"

    # Chat status management

    def start_chat(self) -> None:
        """Start a chat session."""
        self._chat_status = "running"

    def finish_chat(self) -> None:
        """Finish a chat session."""
        if self._chat_status != "success":
            self._chat_status = "success"

    def pause_chat(self, reason: str = "") -> None:
        """
        Pause the chat session.

        Args:
            reason: Optional reason for pausing
        """
        self._chat_status = "pause"
        if reason:
            self.set_state("pause_reason", reason)

    def is_chat_running(self) -> bool:
        """Check if chat is running."""
        return self._chat_status == "running"

    def is_paused(self) -> bool:
        """Check if chat is paused."""
        return self._chat_status == "pause"

    def get_chat_status(self) -> str:
        """Get the chat status."""
        return self._chat_status

    # User answer management

    def set_waiting_user_answer(self, waiting: bool) -> None:
        """
        Set whether waiting for user answer.

        Args:
            waiting: True if waiting for user answer
        """
        self._waiting_user_answer = waiting

    def is_waiting_user_answer(self) -> bool:
        """Check if waiting for user answer."""
        return self._waiting_user_answer

    def set_user_answer(self, answer: str) -> None:
        """
        Set the user's answer.

        Note: This does NOT clear the _waiting_user_answer flag.
        The flag is cleared by the ReactLoop via set_waiting_user_answer(False).

        Args:
            answer: User's answer
        """
        self._user_answer = answer

    def get_user_answer(self) -> str:
        """
        Get the user's answer.

        Returns:
            User's answer
        """
        return self._user_answer

    # Terminal content management

    def set_need_terminal(self, need: bool) -> None:
        """
        Set whether terminal content is needed.

        Args:
            need: True if terminal is needed
        """
        self._need_terminal = need

    def needs_terminal(self) -> bool:
        """Check if terminal content is needed."""
        return self._need_terminal

    def set_terminal_content(self, content: str) -> None:
        """
        Set the terminal content.

        Args:
            content: Terminal output content
        """
        self._terminal_content = content

    def get_terminal_content(self) -> str:
        """
        Get the terminal content.

        Returns:
            Terminal content
        """
        return self._terminal_content

    # Task management

    def add_task(self, task_id: str, task_type: str, task_data: Dict[str, Any]) -> None:
        """
        Add a task to tracking.

        Args:
            task_id: Unique task identifier
            task_type: Task type
            task_data: Task data
        """
        self._tasks.append({
            "id": task_id,
            "type": task_type,
            "data": task_data
        })

    def get_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tracked tasks.

        Returns:
            List of tasks
        """
        return self._tasks.copy()

    def clear_tasks(self) -> None:
        """Clear all tasks."""
        self._tasks.clear()

    def get_last_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the last task.

        Returns:
            Last task or None if no tasks
        """
        return self._tasks[-1] if self._tasks else None

    # Checkpoint management

    def export_checkpoint(self) -> Dict[str, Any]:
        """
        Export current state as checkpoint.

        Returns:
            Checkpoint data dict
        """
        return {
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content if msg.content is not None else "",
                    "metadata": msg.metadata
                }
                for msg in self._messages
            ],
            "state": self._state.copy(),
            "status": self._status,
            "chat_status": self._chat_status,
            "tasks": self._tasks.copy()
        }

    def load_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """
        Load state from checkpoint.

        Args:
            checkpoint: Checkpoint data dict
        """
        self._messages = [
            Message(**msg) for msg in checkpoint.get("messages", [])
        ]
        self._state = checkpoint.get("state", {}).copy()
        self._status = checkpoint.get("status", "running")
        self._chat_status = checkpoint.get("chat_status", "running")
        self._tasks = checkpoint.get("tasks", []).copy()

    def reset(self) -> None:
        """Reset the context to initial state."""
        self._messages.clear()
        self._user_input = ""
        self._state.clear()
        self._status = "running"
        self._tasks.clear()
        self._chat_status = "running"
        self._waiting_user_answer = False
        self._user_answer = ""
        self._need_terminal = False
        self._terminal_content = ""
