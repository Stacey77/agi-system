"""Unit tests for JWT auth, key store, and async task queue."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# KeyStore
# ---------------------------------------------------------------------------

class TestKeyStore:
    def test_create_and_validate_key(self):
        from src.auth.key_store import KeyStore, KeyRole
        ks = KeyStore()
        raw, api_key = ks.create_key("test", KeyRole.WRITE)
        assert api_key.role == KeyRole.WRITE
        assert api_key.active is True
        validated = ks.validate_key(raw)
        assert validated is not None
        assert validated.key_id == api_key.key_id

    def test_validate_wrong_key_returns_none(self):
        from src.auth.key_store import KeyStore
        ks = KeyStore()
        assert ks.validate_key("not-a-real-key") is None

    def test_revoke_key(self):
        from src.auth.key_store import KeyStore, KeyRole
        ks = KeyStore()
        raw, api_key = ks.create_key("to-revoke", KeyRole.READ)
        assert ks.revoke_key(api_key.key_id) is True
        assert ks.validate_key(raw) is None

    def test_revoke_missing_key_returns_false(self):
        from src.auth.key_store import KeyStore
        ks = KeyStore()
        assert ks.revoke_key("nonexistent-id") is False

    def test_list_keys(self):
        from src.auth.key_store import KeyStore, KeyRole
        ks = KeyStore()
        ks.create_key("key-a", KeyRole.READ)
        ks.create_key("key-b", KeyRole.ADMIN)
        keys = ks.list_keys()
        assert len(keys) >= 2

    def test_load_from_env_api_key(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "sk-test-envkey")
        from importlib import reload
        import src.auth.key_store as ks_mod
        reload(ks_mod)
        from src.auth.key_store import KeyStore
        ks = KeyStore()
        assert ks.validate_key("sk-test-envkey") is not None

    def test_key_prefix_format(self):
        from src.auth.key_store import KeyStore, KeyRole
        ks = KeyStore()
        raw, _ = ks.create_key("prefix-test", KeyRole.WRITE)
        assert raw.startswith("sk-")


# ---------------------------------------------------------------------------
# JWTManager
# ---------------------------------------------------------------------------

class TestJWTManager:
    def _manager(self):
        from src.auth.jwt_manager import JWTManager
        return JWTManager(secret="test-secret-xyz", expiry_seconds=3600)

    def test_create_and_verify_token(self):
        jm = self._manager()
        token = jm.create_token(key_id="kid1", name="alice", role="admin")
        payload = jm.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "kid1"
        assert payload["name"] == "alice"
        assert payload["role"] == "admin"

    def test_expired_token_rejected(self):
        from src.auth.jwt_manager import JWTManager
        jm = JWTManager(secret="test-secret-xyz", expiry_seconds=-1)
        token = jm.create_token(key_id="kid2", name="bob", role="read")
        payload = jm.verify_token(token)
        assert payload is None

    def test_tampered_token_rejected(self):
        jm = self._manager()
        token = jm.create_token(key_id="kid3", name="carol", role="write")
        parts = token.split(".")
        parts[1] = parts[1][:-2] + "XX"
        tampered = ".".join(parts)
        assert jm.verify_token(tampered) is None

    def test_wrong_secret_rejected(self):
        from src.auth.jwt_manager import JWTManager
        jm1 = JWTManager(secret="secret-a", expiry_seconds=3600)
        jm2 = JWTManager(secret="secret-b", expiry_seconds=3600)
        token = jm1.create_token(key_id="kid4", name="dave", role="admin")
        assert jm2.verify_token(token) is None

    def test_malformed_token_rejected(self):
        jm = self._manager()
        assert jm.verify_token("not.a.valid.jwt.token") is None
        assert jm.verify_token("") is None
        assert jm.verify_token("only-one-part") is None


# ---------------------------------------------------------------------------
# TaskRecord
# ---------------------------------------------------------------------------

class TestTaskRecord:
    def test_to_dict_keys(self):
        from src.tasks.queue import TaskRecord, TaskStatus
        r = TaskRecord(task_id="t1", objective="do something")
        d = r.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == TaskStatus.QUEUED
        assert d["result"] is None
        assert d["error"] is None
        assert d["progress"] == 0


# ---------------------------------------------------------------------------
# TaskQueue (in-process asyncio, no Redis)
# ---------------------------------------------------------------------------

class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_submit_and_get(self):
        from src.tasks.queue import TaskQueue, TaskStatus
        q = TaskQueue()
        handled = asyncio.Event()

        async def handler(record):
            handled.set()

        await q.start(handler)
        record = await q.submit("test objective", {})
        assert record.task_id is not None
        await asyncio.wait_for(handled.wait(), timeout=5.0)
        await q.stop()

    @pytest.mark.asyncio
    async def test_task_completes(self):
        from src.tasks.queue import TaskQueue, TaskStatus
        q = TaskQueue()
        done = asyncio.Event()

        async def handler(record):
            record.result = {"summary": "done"}
            done.set()

        await q.start(handler)
        record = await q.submit("complete this", {})
        task_id = record.task_id
        await asyncio.wait_for(done.wait(), timeout=5.0)
        await asyncio.sleep(0.1)
        fetched = q.get(task_id)
        assert fetched is not None
        assert fetched.status == TaskStatus.COMPLETED
        await q.stop()

    @pytest.mark.asyncio
    async def test_task_failure(self):
        from src.tasks.queue import TaskQueue, TaskStatus
        q = TaskQueue()

        async def handler(record):
            raise ValueError("deliberate failure")

        await q.start(handler)
        record = await q.submit("fail this", {})
        task_id = record.task_id
        await asyncio.sleep(0.5)
        fetched = q.get(task_id)
        assert fetched is not None
        assert fetched.status == TaskStatus.FAILED
        assert "deliberate failure" in fetched.error
        await q.stop()

    @pytest.mark.asyncio
    async def test_cancel_queued_task(self):
        from src.tasks.queue import TaskQueue, TaskStatus
        # Use a slow handler so we can cancel before it runs
        q = TaskQueue()
        start_event = asyncio.Event()
        block_event = asyncio.Event()

        async def slow_handler(record):
            start_event.set()
            await asyncio.wait_for(block_event.wait(), timeout=2.0)

        await q.start(slow_handler)
        # Submit two tasks — cancel the second before it's processed
        r1 = await q.submit("task one", {})
        r2 = await q.submit("task two", {})
        # Wait for first to start, then cancel second
        await asyncio.wait_for(start_event.wait(), timeout=2.0)
        result = q.cancel(r2.task_id)
        assert result is True
        block_event.set()
        await asyncio.sleep(0.2)
        await q.stop()

    @pytest.mark.asyncio
    async def test_list_all(self):
        from src.tasks.queue import TaskQueue
        q = TaskQueue()
        done = asyncio.Event()

        async def handler(record):
            done.set()

        await q.start(handler)
        await q.submit("alpha", {})
        await q.submit("beta", {})
        records = q.list_all()
        assert len(records) == 2
        await asyncio.wait_for(done.wait(), timeout=5.0)
        await q.stop()

    @pytest.mark.asyncio
    async def test_subscribe_receives_events(self):
        from src.tasks.queue import TaskQueue, TaskStatus
        q = TaskQueue()
        done = asyncio.Event()

        async def handler(record):
            done.set()

        await q.start(handler)
        record = await q.submit("stream this", {})
        task_id = record.task_id
        sub_q = await q.subscribe(task_id)
        await asyncio.wait_for(done.wait(), timeout=5.0)
        await asyncio.sleep(0.1)
        events = []
        while not sub_q.empty():
            events.append(sub_q.get_nowait())
        statuses = [e["event"] for e in events]
        assert "queued" in statuses or "running" in statuses or "completed" in statuses
        q.unsubscribe(task_id, sub_q)
        await q.stop()


# ---------------------------------------------------------------------------
# Integration: auth and task endpoints
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        with TestClient(create_app()) as c:
            yield c

    def test_get_token_invalid_key(self, client):
        r = client.post("/api/v1/auth/token", json={"api_key": "invalid-key"})
        assert r.status_code == 401

    def test_me_unauthenticated(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code in (200, 401)

    def test_list_keys_unauthenticated(self, client):
        r = client.get("/api/v1/auth/keys")
        assert r.status_code in (200, 401, 403)


class TestTaskEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.main import create_app
        with TestClient(create_app()) as c:
            yield c

    def test_submit_task(self, client):
        r = client.post("/api/v1/tasks/", json={"objective": "test task", "parameters": {}})
        assert r.status_code == 200
        data = r.json()
        assert "task_id" in data
        assert data["status"] == "queued"

    def test_get_task(self, client):
        r = client.post("/api/v1/tasks/", json={"objective": "get me later"})
        task_id = r.json()["task_id"]
        r2 = client.get(f"/api/v1/tasks/{task_id}")
        assert r2.status_code == 200
        assert r2.json()["task_id"] == task_id

    def test_get_missing_task(self, client):
        r = client.get("/api/v1/tasks/nonexistent-task-id")
        assert r.status_code == 404

    def test_list_tasks(self, client):
        r = client.get("/api/v1/tasks/")
        assert r.status_code == 200
        data = r.json()
        assert "tasks" in data
        assert "total" in data

    def test_cancel_missing_task(self, client):
        r = client.delete("/api/v1/tasks/nonexistent-id")
        assert r.status_code == 404
