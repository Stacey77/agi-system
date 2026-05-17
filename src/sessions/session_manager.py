from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AgentSession:
    session_id: str
    agent_name: str
    created_at: str
    messages: List[Dict[str, Any]] = field(default_factory=list)


class SessionManager:
    def __init__(self, store: Optional[Any] = None) -> None:
        self._store = store
        if store is not None:
            self._sessions: Dict[str, AgentSession] = store.load_all()
        else:
            self._sessions = {}

    def create_session(self, agent_name: str) -> AgentSession:
        session_id = str(uuid.uuid4())
        session = AgentSession(
            session_id=session_id,
            agent_name=agent_name,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._sessions[session_id] = session
        if self._store:
            self._store.save(session)
        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[AgentSession]:
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        if self._store:
            self._store.delete(session_id)
        return True

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.messages.append({"role": role, "content": content})
            if self._store:
                self._store.save(session)
