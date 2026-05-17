"""Tests for the memory REST API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.memory.memory_manager import MemoryManager
from src.memory.hybrid_memory import HybridMemory


# ---------------------------------------------------------------------------
# MemoryManager unit tests
# ---------------------------------------------------------------------------

class TestMemoryManager:
    def test_store_and_retrieve_short_term(self):
        mm = MemoryManager()
        mm.store("foo", "bar", "short_term")
        assert mm.retrieve("foo", "short_term") == "bar"

    def test_retrieve_missing_key_returns_none(self):
        mm = MemoryManager()
        assert mm.retrieve("nonexistent", "short_term") is None

    def test_search_short_term(self):
        mm = MemoryManager()
        mm.store("python_key", "python_value", "short_term")
        mm.store("other", "something", "short_term")
        results = mm.search("python", "short_term")
        assert any("python" in str(r) for r in results)

    def test_invalid_memory_type_raises(self):
        mm = MemoryManager()
        with pytest.raises(ValueError, match="Unknown memory_type"):
            mm.store("k", "v", "invalid_type")

    def test_conversation_add_and_get(self):
        mm = MemoryManager()
        mm.add_conversation_message("user", "hello")
        mm.add_conversation_message("assistant", "hi there")
        ctx = mm.get_conversation_context(5)
        assert len(ctx) == 2

    def test_conversation_clear(self):
        mm = MemoryManager()
        mm.add_conversation_message("user", "hello")
        mm.clear_conversation()
        ctx = mm.get_conversation_context(5)
        assert ctx == []


# ---------------------------------------------------------------------------
# Fixture: TestClient with real MemoryManager + mock auth
# ---------------------------------------------------------------------------

def _make_api_key():
    from src.auth.key_store import KeyRole
    key = MagicMock()
    key.role = KeyRole("admin")
    key.key_id = "k1"
    key.name = "test"
    return key


@pytest.fixture()
def mem_client():
    from src.api.main import create_app
    app = create_app()
    mm = MemoryManager()
    hm = HybridMemory()

    with TestClient(app, raise_server_exceptions=True) as c:
        app.state.memory_manager = mm
        app.state.hybrid_memory = hm
        app.state.key_store = MagicMock()
        app.state.key_store.validate_key.return_value = _make_api_key()
        app.state.jwt_manager = MagicMock()
        app.state.jwt_manager.verify_token.return_value = None
        yield c


HEADERS = {"X-API-Key": "sk-test"}


# ---------------------------------------------------------------------------
# Short-term memory endpoints
# ---------------------------------------------------------------------------

class TestShortTermEndpoints:
    def test_list_short_term_empty(self, mem_client):
        resp = mem_client.get("/api/v1/memory/short-term", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["memory"] == {}

    def test_store_and_list(self, mem_client):
        mem_client.post("/api/v1/memory/store", headers=HEADERS,
                        json={"key": "x", "value": "42", "memory_type": "short_term"})
        resp = mem_client.get("/api/v1/memory/short-term", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()["memory"]["x"] == "42"

    def test_delete_key(self, mem_client):
        mem_client.post("/api/v1/memory/store", headers=HEADERS,
                        json={"key": "delme", "value": "v", "memory_type": "short_term"})
        resp = mem_client.delete("/api/v1/memory/short-term/delme", headers=HEADERS)
        assert resp.status_code == 200
        resp2 = mem_client.get("/api/v1/memory/short-term", headers=HEADERS)
        assert "delme" not in resp2.json()["memory"]

    def test_delete_missing_key_404(self, mem_client):
        resp = mem_client.delete("/api/v1/memory/short-term/noexist", headers=HEADERS)
        assert resp.status_code == 404

    def test_clear_short_term(self, mem_client):
        mem_client.post("/api/v1/memory/store", headers=HEADERS,
                        json={"key": "a", "value": "1", "memory_type": "short_term"})
        mem_client.post("/api/v1/memory/store", headers=HEADERS,
                        json={"key": "b", "value": "2", "memory_type": "short_term"})
        resp = mem_client.delete("/api/v1/memory/short-term", headers=HEADERS)
        assert resp.status_code == 200
        resp2 = mem_client.get("/api/v1/memory/short-term", headers=HEADERS)
        assert resp2.json()["memory"] == {}


# ---------------------------------------------------------------------------
# Store / retrieve / search endpoints
# ---------------------------------------------------------------------------

class TestStoreRetrieveSearch:
    def test_store_and_retrieve(self, mem_client):
        mem_client.post("/api/v1/memory/store", headers=HEADERS,
                        json={"key": "mykey", "value": "myval"})
        resp = mem_client.get("/api/v1/memory/retrieve", headers=HEADERS,
                              params={"key": "mykey", "memory_type": "short_term"})
        assert resp.status_code == 200
        assert resp.json()["value"] == "myval"

    def test_store_invalid_memory_type_422(self, mem_client):
        resp = mem_client.post("/api/v1/memory/store", headers=HEADERS,
                               json={"key": "k", "value": "v", "memory_type": "invalid"})
        assert resp.status_code == 422

    def test_search_short_term(self, mem_client):
        mem_client.post("/api/v1/memory/store", headers=HEADERS,
                        json={"key": "search_key", "value": "searchable content"})
        resp = mem_client.get("/api/v1/memory/search", headers=HEADERS,
                              params={"query": "searchable", "memory_type": "short_term"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["query"] == "searchable"


# ---------------------------------------------------------------------------
# Conversation endpoints
# ---------------------------------------------------------------------------

class TestConversationEndpoints:
    def test_add_and_get_conversation(self, mem_client):
        mem_client.post("/api/v1/memory/conversation", headers=HEADERS,
                        json={"role": "user", "content": "hello"})
        resp = mem_client.get("/api/v1/memory/conversation", headers=HEADERS, params={"n": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1

    def test_clear_conversation(self, mem_client):
        mem_client.post("/api/v1/memory/conversation", headers=HEADERS,
                        json={"role": "user", "content": "test"})
        mem_client.delete("/api/v1/memory/conversation", headers=HEADERS)
        resp = mem_client.get("/api/v1/memory/conversation", headers=HEADERS)
        assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# Hybrid memory endpoints
# ---------------------------------------------------------------------------

class TestHybridMemoryEndpoints:
    def test_store_shared_and_get_context(self, mem_client):
        mem_client.post("/api/v1/memory/hybrid/store", headers=HEADERS,
                        json={"documents": ["Python is a programming language"]})
        resp = mem_client.post("/api/v1/memory/hybrid/context", headers=HEADERS,
                               json={"agent_id": "agent_a", "query": "Python", "k": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "agent_a"
        assert "context" in data

    def test_store_agent_specific(self, mem_client):
        resp = mem_client.post("/api/v1/memory/hybrid/store", headers=HEADERS,
                               json={"documents": ["agent doc"], "agent_id": "agent_b"})
        assert resp.status_code == 200
        assert "agent_b" in resp.json()["message"]

    def test_clear_agent_context(self, mem_client):
        mem_client.post("/api/v1/memory/hybrid/store", headers=HEADERS,
                        json={"documents": ["some doc"], "agent_id": "agent_c"})
        resp = mem_client.delete("/api/v1/memory/hybrid/agent_c", headers=HEADERS)
        assert resp.status_code == 200
        assert "agent_c" in resp.json()["message"]
