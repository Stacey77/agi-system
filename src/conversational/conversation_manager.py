"""SQLite-backed conversation session manager."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    import aiosqlite  # type: ignore
    _AIOSQLITE = True
except ImportError:
    import sqlite3
    _AIOSQLITE = False


class ConversationManager:
    """Manages conversation sessions and their message history using SQLite."""

    def __init__(self, db_path: str = "conversations.db") -> None:
        self._db_path = db_path
        self._initialized = False

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        await self._init_db()
        self._initialized = True

    async def _init_db(self) -> None:
        ddl = [
            """CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                metadata TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                tokens INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_name)",
        ]
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                for stmt in ddl:
                    await db.execute(stmt)
                await db.commit()
        else:
            def _sync() -> None:
                conn = sqlite3.connect(self._db_path)
                try:
                    for stmt in ddl:
                        conn.execute(stmt)
                    conn.commit()
                finally:
                    conn.close()
            await asyncio.to_thread(_sync)

    # ── sessions ──────────────────────────────────────────────────────────────

    async def create_session(
        self, agent_name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        await self._ensure_init()
        now = time.time()
        session_id = str(uuid.uuid4())
        meta_str = json.dumps(metadata or {})
        row = (session_id, agent_name, now, now, meta_str)
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO sessions VALUES (?,?,?,?,?)", row
                )
                await db.commit()
        else:
            def _sync() -> None:
                conn = sqlite3.connect(self._db_path)
                try:
                    conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", row)
                    conn.commit()
                finally:
                    conn.close()
            await asyncio.to_thread(_sync)
        return {
            "session_id": session_id,
            "agent_name": agent_name,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
            "message_count": 0,
        }

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_init()
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT s.*, COUNT(m.id) as message_count "
                    "FROM sessions s LEFT JOIN messages m ON s.session_id=m.session_id "
                    "WHERE s.session_id=? GROUP BY s.session_id",
                    (session_id,),
                ) as cur:
                    row = await cur.fetchone()
                    return _row_to_session(row) if row else None
        else:
            def _sync() -> Optional[Dict[str, Any]]:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                try:
                    cur = conn.execute(
                        "SELECT s.*, COUNT(m.id) as message_count "
                        "FROM sessions s LEFT JOIN messages m ON s.session_id=m.session_id "
                        "WHERE s.session_id=? GROUP BY s.session_id",
                        (session_id,),
                    )
                    row = cur.fetchone()
                    return _row_to_session(row) if row else None
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    async def list_sessions(
        self,
        agent_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        await self._ensure_init()
        where = "WHERE s.agent_name=?" if agent_name else ""
        params: tuple = (agent_name, limit, offset) if agent_name else (limit, offset)
        sql = (
            f"SELECT s.*, COUNT(m.id) as message_count "
            f"FROM sessions s LEFT JOIN messages m ON s.session_id=m.session_id "
            f"{where} GROUP BY s.session_id "
            f"ORDER BY s.updated_at DESC LIMIT ? OFFSET ?"
        )
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, params) as cur:
                    rows = await cur.fetchall()
                    return [_row_to_session(r) for r in rows]
        else:
            def _sync() -> List[Dict[str, Any]]:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                try:
                    return [_row_to_session(r) for r in conn.execute(sql, params).fetchall()]
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    async def delete_session(self, session_id: str) -> bool:
        await self._ensure_init()
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                cur = await db.execute(
                    "DELETE FROM sessions WHERE session_id=?", (session_id,)
                )
                await db.execute(
                    "DELETE FROM messages WHERE session_id=?", (session_id,)
                )
                await db.commit()
                return cur.rowcount > 0
        else:
            def _sync() -> bool:
                conn = sqlite3.connect(self._db_path)
                try:
                    n = conn.execute(
                        "DELETE FROM sessions WHERE session_id=?", (session_id,)
                    ).rowcount
                    conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
                    conn.commit()
                    return n > 0
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    # ── messages ──────────────────────────────────────────────────────────────

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
    ) -> Dict[str, Any]:
        await self._ensure_init()
        now = time.time()
        row = (session_id, role, content, now, tokens)
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                cur = await db.execute(
                    "INSERT INTO messages (session_id,role,content,timestamp,tokens) VALUES (?,?,?,?,?)",
                    row,
                )
                await db.execute(
                    "UPDATE sessions SET updated_at=? WHERE session_id=?",
                    (now, session_id),
                )
                await db.commit()
                msg_id = cur.lastrowid
        else:
            def _sync() -> int:
                conn = sqlite3.connect(self._db_path)
                try:
                    mid = conn.execute(
                        "INSERT INTO messages (session_id,role,content,timestamp,tokens) VALUES (?,?,?,?,?)",
                        row,
                    ).lastrowid
                    conn.execute(
                        "UPDATE sessions SET updated_at=? WHERE session_id=?",
                        (now, session_id),
                    )
                    conn.commit()
                    return mid
                finally:
                    conn.close()
            msg_id = await asyncio.to_thread(_sync)
        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": now,
            "tokens": tokens,
        }

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        await self._ensure_init()
        sql = (
            "SELECT * FROM messages WHERE session_id=? "
            "ORDER BY timestamp ASC LIMIT ? OFFSET ?"
        )
        params = (session_id, limit, offset)
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, params) as cur:
                    return [dict(r) for r in await cur.fetchall()]
        else:
            def _sync() -> List[Dict[str, Any]]:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                try:
                    return [dict(r) for r in conn.execute(sql, params).fetchall()]
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    async def get_context_window(
        self, session_id: str, max_tokens: int = 4000
    ) -> List[Dict[str, Any]]:
        msgs = await self.get_messages(session_id, limit=500)
        result: List[Dict[str, Any]] = []
        budget = max_tokens
        for msg in reversed(msgs):
            approx = len(msg.get("content", "")) // 4 + 1
            if approx > budget:
                break
            budget -= approx
            result.insert(0, msg)
        return result

    async def clear_messages(self, session_id: str) -> int:
        await self._ensure_init()
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                cur = await db.execute(
                    "DELETE FROM messages WHERE session_id=?", (session_id,)
                )
                await db.commit()
                return cur.rowcount
        else:
            def _sync() -> int:
                conn = sqlite3.connect(self._db_path)
                try:
                    n = conn.execute(
                        "DELETE FROM messages WHERE session_id=?", (session_id,)
                    ).rowcount
                    conn.commit()
                    return n
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    async def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"ConversationManager(db={self._db_path!r})"


def _row_to_session(row: Any) -> Dict[str, Any]:
    d = dict(row)
    try:
        d["metadata"] = json.loads(d.get("metadata") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["metadata"] = {}
    return d
