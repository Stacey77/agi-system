from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class EvalStore:
    def __init__(self, db_path: str = "evals.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS evals ("
            "eval_id TEXT PRIMARY KEY, "
            "data TEXT NOT NULL, "
            "created_at REAL NOT NULL)"
        )
        self._conn.commit()

    def save(self, result: Dict[str, Any]) -> None:
        eval_id = result["eval_id"]
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO evals (eval_id, data, created_at) VALUES (?, ?, ?)",
                (eval_id, json.dumps(result), time.time()),
            )
            self._conn.commit()

    def load_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM evals ORDER BY created_at ASC"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, eval_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM evals WHERE eval_id = ?", (eval_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, eval_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM evals WHERE eval_id = ?", (eval_id,)
            )
            self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()
