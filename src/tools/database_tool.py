"""Database tool — SQL query execution with connection management."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.tools.base_tool import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class DatabaseTool(BaseTool):
    """Executes SQL queries against a configured database."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._database_url = database_url
        self._connection: Optional[Any] = None

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="database",
            description="Execute SQL queries and manage database connections",
            parameters={
                "required": ["query"],
                "optional": ["params", "fetch"],
                "properties": {
                    "query": {"type": "string", "description": "SQL query to execute"},
                    "params": {"type": "array", "description": "Query parameters"},
                    "fetch": {
                        "type": "string",
                        "enum": ["all", "one", "none"],
                        "default": "all",
                    },
                },
            },
            return_type="Dict",
            category="integration",
            required_permissions=["database_read"],
        )

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        if not self.validate_parameters(**kwargs):
            return {"error": "Missing required parameters", "rows": []}

        query = kwargs["query"]
        params = kwargs.get("params", [])
        fetch = kwargs.get("fetch", "all")

        try:
            conn = self._get_connection()
            rows = self._run_query(conn, query, params, fetch)
            return {"query": query, "rows": rows, "row_count": len(rows) if isinstance(rows, list) else 0}
        except Exception as exc:  # noqa: BLE001
            logger.error("Database query failed: %s", exc)
            return {"error": str(exc), "rows": []}

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_connection(self) -> Any:
        """Return an open database connection, creating one if necessary."""
        if self._connection is not None:
            return self._connection
        if not self._database_url:
            # Return a mock connection for testing / when no DB is configured
            return _MockConnection()
        try:
            import sqlalchemy  # type: ignore[import]

            engine = sqlalchemy.create_engine(self._database_url)
            self._connection = engine.connect()
            return self._connection
        except ImportError:
            logger.warning("SQLAlchemy not installed; using mock connection")
            return _MockConnection()

    def _run_query(
        self,
        conn: Any,
        query: str,
        params: List[Any],
        fetch: str,
    ) -> Any:
        if isinstance(conn, _MockConnection):
            return conn.execute(query, params, fetch)
        cursor = conn.execute(query, params)
        if fetch == "all":
            return [dict(row) for row in cursor.fetchall()]
        if fetch == "one":
            row = cursor.fetchone()
            return dict(row) if row else None
        return []

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._connection = None


class _MockConnection:
    """In-memory mock connection for testing without a real database."""

    def execute(self, query: str, params: List[Any], fetch: str) -> Any:
        logger.debug("MockConnection executing: %s (params=%s)", query, params)
        if fetch == "one":
            return {"id": 1, "value": "mock_result"}
        if fetch == "none":
            return []
        return [{"id": 1, "value": "mock_result"}]
