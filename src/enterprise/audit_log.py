"""SQLite-backed audit log for enterprise governance."""

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


class AuditLog:
    """Append-only audit log with query and purge capabilities."""

    def __init__(self, db_path: str = "audit.db") -> None:
        self._db_path = db_path
        self._initialized = False

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        await self._init_db()
        self._initialized = True

    async def _init_db(self) -> None:
        ddl = [
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT DEFAULT '',
                details TEXT,
                ip_address TEXT DEFAULT '',
                status TEXT DEFAULT 'success'
            )""",
            "CREATE INDEX IF NOT EXISTS idx_audit_actor ON events(actor)",
            "CREATE INDEX IF NOT EXISTS idx_audit_action ON events(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_ts ON events(timestamp)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_eid ON events(event_id)",
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

    async def log(
        self,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "",
        status: str = "success",
    ) -> str:
        await self._ensure_init()
        event_id = str(uuid.uuid4())
        now = time.time()
        details_str = json.dumps(details or {})
        row = (event_id, now, actor, action, resource_type, resource_id, details_str, ip_address, status)
        sql = (
            "INSERT INTO events (event_id,timestamp,actor,action,resource_type,"
            "resource_id,details,ip_address,status) VALUES (?,?,?,?,?,?,?,?,?)"
        )
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(sql, row)
                await db.commit()
        else:
            def _sync() -> None:
                conn = sqlite3.connect(self._db_path)
                try:
                    conn.execute(sql, row)
                    conn.commit()
                finally:
                    conn.close()
            await asyncio.to_thread(_sync)
        return event_id

    async def query(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        await self._ensure_init()
        conditions: List[str] = []
        params: List[Any] = []
        if actor:
            conditions.append("actor=?"); params.append(actor)
        if action:
            conditions.append("action=?"); params.append(action)
        if resource_type:
            conditions.append("resource_type=?"); params.append(resource_type)
        if start_time is not None:
            conditions.append("timestamp>=?"); params.append(start_time)
        if end_time is not None:
            conditions.append("timestamp<=?"); params.append(end_time)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        count_sql = f"SELECT COUNT(*) FROM events {where}"
        data_sql = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"

        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(count_sql, params) as cur:
                    total = (await cur.fetchone())[0]
                async with db.execute(data_sql, params + [limit, offset]) as cur:
                    events = [_row_to_event(r) for r in await cur.fetchall()]
        else:
            def _sync() -> tuple:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                try:
                    t = conn.execute(count_sql, params).fetchone()[0]
                    rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
                    return t, [_row_to_event(r) for r in rows]
                finally:
                    conn.close()
            total, events = await asyncio.to_thread(_sync)

        return {"events": events, "total": total, "limit": limit, "offset": offset}

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_init()
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)) as cur:
                    row = await cur.fetchone()
                    return _row_to_event(row) if row else None
        else:
            def _sync() -> Optional[Dict[str, Any]]:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                try:
                    row = conn.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
                    return _row_to_event(row) if row else None
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    async def purge_before(self, timestamp: float) -> int:
        await self._ensure_init()
        if _AIOSQLITE:
            async with aiosqlite.connect(self._db_path) as db:
                cur = await db.execute("DELETE FROM events WHERE timestamp<?", (timestamp,))
                await db.commit()
                return cur.rowcount
        else:
            def _sync() -> int:
                conn = sqlite3.connect(self._db_path)
                try:
                    n = conn.execute("DELETE FROM events WHERE timestamp<?", (timestamp,)).rowcount
                    conn.commit()
                    return n
                finally:
                    conn.close()
            return await asyncio.to_thread(_sync)

    async def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"AuditLog(db={self._db_path!r})"


def _row_to_event(row: Any) -> Dict[str, Any]:
    d = dict(row)
    try:
        d["details"] = json.loads(d.get("details") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["details"] = {}
    return d
