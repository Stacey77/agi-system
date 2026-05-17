"""SQLite-backed persistence for AgentSession."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Dict, List, Optional

from src.sessions.session_manager import AgentSession

logger = logging.getLogger(__name__)

_CREATE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    messages    TEXT NOT NULL DEFAULT '[]'
);
"""


class SessionStore:
    def __init__(self, db_path: str = "sessions.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init()

    def _init(self) -> None:
        try:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute(_CREATE)
            self._conn.commit()
            logger.info("SessionStore initialised at %s", self._db_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SessionStore init failed (%s) — running without persistence", exc)
            self._conn = None

    def save(self, session: AgentSession) -> None:
        if self._conn is None:
            return
        with self._lock:
            try:
                self._conn.execute(
                    """INSERT INTO sessions (session_id, agent_name, created_at, messages)
                       VALUES (?,?,?,?)
                       ON CONFLICT(session_id) DO UPDATE SET messages=excluded.messages""",
                    (session.session_id, session.agent_name, session.created_at,
                     json.dumps(session.messages)),
                )
                self._conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("SessionStore.save failed: %s", exc)

    def delete(self, session_id: str) -> None:
        if self._conn is None:
            return
        with self._lock:
            try:
                self._conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                self._conn.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("SessionStore.delete failed: %s", exc)

    def load_all(self) -> Dict[str, AgentSession]:
        if self._conn is None:
            return {}
        sessions: Dict[str, AgentSession] = {}
        with self._lock:
            try:
                cur = self._conn.execute(
                    "SELECT session_id, agent_name, created_at, messages FROM sessions"
                )
                for row in cur.fetchall():
                    session_id, agent_name, created_at, messages_json = row
                    s = AgentSession(
                        session_id=session_id,
                        agent_name=agent_name,
                        created_at=created_at,
                        messages=json.loads(messages_json),
                    )
                    sessions[session_id] = s
            except Exception as exc:  # noqa: BLE001
                logger.warning("SessionStore.load_all failed: %s", exc)
        return sessions

    def close(self) -> None:
        if self._conn:
            with self._lock:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
            self._conn = None
