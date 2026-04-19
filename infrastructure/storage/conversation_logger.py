"""
Conversation logger - persists conversation messages to JSONL files.

Each message is appended as a single JSON line:
  {"ts": "2026-04-05T10:23:44", "role": "user", "content": "...", "metadata": {...}}

File layout:
  ~/.termbot/conversations/{agent_id}/{session_id}/chat.jsonl
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from infrastructure.logging import get_logger

if TYPE_CHECKING:
    from agent.context import Message

logger = get_logger("storage.conversation")


class ConversationLogger:
    """Appends conversation messages to a JSONL file."""

    def __init__(self, session_id: str, agent_id: str = "default", base_dir: Optional[str] = None) -> None:
        if base_dir is None:
            base_dir = str(Path.home() / ".termbot" / "conversations")

        dir_path = Path(base_dir).expanduser() / agent_id / session_id
        dir_path.mkdir(parents=True, exist_ok=True)

        self._file_path = dir_path / "chat.jsonl"
        self._file = open(self._file_path, "a", encoding="utf-8")  # pylint: disable=consider-using-with
        logger.debug("Conversation logger started", path=str(self._file_path))

    def log(self, message: "Message") -> None:
        """Append a message record to the JSONL file."""
        record: dict = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "role": message.role,
            "content": message.content,
        }
        if message.metadata:
            record["metadata"] = message.metadata

        try:
            self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._file.flush()
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Failed to write conversation log", error=str(e))

    def close(self) -> None:
        """Close the log file."""
        try:
            self._file.close()
        except Exception:  # pylint: disable=broad-except
            pass

    @property
    def file_path(self) -> Path:
        """Path to the current log file."""
        return self._file_path


def create_conversation_logger(session_id: str, agent_id: str = "default") -> Optional[ConversationLogger]:
    """
    Create a ConversationLogger based on config.

    Returns None if conversations are disabled in config.
    """
    from infrastructure.config.settings import settings  # avoid circular import

    conv_config = settings.get("conversations", {})
    if not conv_config.get("enabled", True):
        return None

    base_dir = conv_config.get("base_dir", "~/.termbot/conversations")
    return ConversationLogger(session_id=session_id, agent_id=agent_id, base_dir=base_dir)
