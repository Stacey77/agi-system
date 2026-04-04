"""IDE session management — tracks active vibecoding sessions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionState(str, Enum):
    """Lifecycle state of an IDE session."""

    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"


@dataclass
class IDESession:
    """Represents a single vibecoding IDE session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "python"
    context: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
    state: SessionState = SessionState.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_interaction(self, role: str, content: str) -> None:
        """Append an interaction to the session history."""
        self.history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.updated_at = datetime.now(timezone.utc)

    def close(self) -> None:
        """Mark the session as closed."""
        self.state = SessionState.CLOSED
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "language": self.language,
            "state": self.state,
            "context_length": len(self.context),
            "history_length": len(self.history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class IDESessionManager:
    """Manages the lifecycle of vibecoding IDE sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, IDESession] = {}

    def create_session(
        self,
        language: str = "python",
        context: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IDESession:
        """Create and register a new IDE session."""
        session = IDESession(
            language=language,
            context=context,
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[IDESession]:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        """Close a session. Returns True if it existed."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.close()
        return True

    def list_sessions(self, state: Optional[SessionState] = None) -> List[IDESession]:
        """Return all sessions, optionally filtered by state."""
        sessions = list(self._sessions.values())
        if state is not None:
            sessions = [s for s in sessions if s.state == state]
        return sessions

    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.state == SessionState.ACTIVE)
