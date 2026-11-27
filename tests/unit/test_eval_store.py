"""Unit tests for EvalStore persistence and eval result deletion.

Regression coverage for the Devin Review findings on PR #26:
- ``EvalStore.close()`` must not raise on double-close so shutdown can
  continue cleaning up other resources.
- ``DELETE /api/v1/eval/results/{id}`` must also evict the entry from the
  in-memory ``eval_results`` dict, not just the persistent store.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.eval.eval_store import EvalStore


def _record(eval_id: str) -> dict:
    return {"eval_id": eval_id, "agent": "research_agent", "score": 1.0}


def test_eval_store_save_get_delete(tmp_path):
    store = EvalStore(db_path=str(tmp_path / "evals.db"))
    store.save(_record("a"))
    store.save(_record("b"))

    assert store.get("a") == _record("a")
    assert {r["eval_id"] for r in store.load_all()} == {"a", "b"}

    assert store.delete("a") is True
    assert store.get("a") is None
    assert store.delete("a") is False
    store.close()


def test_eval_store_close_is_idempotent(tmp_path):
    store = EvalStore(db_path=str(tmp_path / "evals.db"))
    store.close()
    # A second close must not raise so the shutdown sequence can continue.
    store.close()


class TestDeleteEvalResult:
    @pytest.fixture(scope="class")
    def client(self):
        with TestClient(create_app()) as c:
            yield c

    def test_delete_removes_from_in_memory_dict(self, client):
        run = client.post("/api/v1/eval/run", json={"agent_name": "research_agent"})
        assert run.status_code == 200
        eval_id = run.json()["eval_id"]

        eval_results = client.app.state.eval_results
        assert eval_id in eval_results

        deleted = client.delete(f"/api/v1/eval/results/{eval_id}")
        assert deleted.status_code == 200
        assert eval_id not in eval_results

        missing = client.delete(f"/api/v1/eval/results/{eval_id}")
        assert missing.status_code == 404
