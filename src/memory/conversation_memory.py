"""Conversation memory — session-based context with a configurable sliding window."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single conversation message."""

    role: str  # "user" | "assistant" | "system"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """Maintains a rolling window of conversation messages per session."""

    def __init__(self, window_size: int = 20) -> None:
        self._window_size = window_size
        self._messages: List[Message] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """Append a message, evicting the oldest if the window is full."""
        msg = Message(role=role, content=content, metadata=metadata)
        self._messages.append(msg)
        if len(self._messages) > self._window_size:
            self._messages.pop(0)
        logger.debug("ConversationMemory: added message (role=%s)", role)

    def get_messages(self) -> List[Message]:
        """Return all current messages."""
        return list(self._messages)

    def get_recent_context(self, n: int = 5) -> List[Message]:
        """Return the *n* most recent messages."""
        return self._messages[-n:]

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        logger.debug("ConversationMemory cleared")

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Serialise messages to a list of dicts."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def __len__(self) -> int:
        return len(self._messages)
