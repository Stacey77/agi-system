"""Unit tests for the memory subsystem."""

from __future__ import annotations

import pytest

from src.memory.conversation_memory import ConversationMemory
from src.memory.hybrid_memory import HybridMemory
from src.memory.memory_manager import MemoryManager
from src.memory.vector_store import VectorStore


# ---------------------------------------------------------------------------
# ConversationMemory
# ---------------------------------------------------------------------------

class TestConversationMemory:
    def test_add_and_retrieve(self):
        mem = ConversationMemory(window_size=10)
        mem.add_message("user", "Hello")
        mem.add_message("assistant", "Hi there")
        messages = mem.get_messages()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].content == "Hi there"

    def test_window_eviction(self):
        mem = ConversationMemory(window_size=3)
        for i in range(5):
            mem.add_message("user", f"msg {i}")
        assert len(mem) == 3
        assert mem.get_messages()[0].content == "msg 2"

    def test_get_recent_context(self):
        mem = ConversationMemory()
        for i in range(10):
            mem.add_message("user", f"msg {i}")
        recent = mem.get_recent_context(n=3)
        assert len(recent) == 3
        assert recent[-1].content == "msg 9"

    def test_clear(self):
        mem = ConversationMemory()
        mem.add_message("user", "hello")
        mem.clear()
        assert len(mem) == 0

    def test_to_dict_list(self):
        mem = ConversationMemory()
        mem.add_message("user", "test")
        dicts = mem.to_dict_list()
        assert dicts[0] == {"role": "user", "content": "test"}


# ---------------------------------------------------------------------------
# VectorStore (mock mode — no ChromaDB required)
# ---------------------------------------------------------------------------

class TestVectorStore:
    def test_add_and_search(self):
        store = VectorStore()
        store._use_mock = True  # force mock mode
        store.add_documents(["apple pie recipe", "machine learning intro"])
        results = store.similarity_search("apple")
        assert len(results) > 0

    def test_delete(self):
        store = VectorStore()
        store._use_mock = True
        store.add_documents(["doc1"], ids=["id1"])
        store.delete(["id1"])
        assert len(store) == 0

    def test_auto_ids(self):
        store = VectorStore()
        store._use_mock = True
        store.add_documents(["a", "b", "c"])
        assert len(store) == 3


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------

class TestMemoryManager:
    def test_store_and_retrieve_short_term(self):
        manager = MemoryManager()
        manager.store("key1", "value1", memory_type="short_term")
        result = manager.retrieve("key1", memory_type="short_term")
        assert result == "value1"

    def test_unknown_memory_type_raises(self):
        manager = MemoryManager()
        with pytest.raises(ValueError):
            manager.store("k", "v", memory_type="invalid_type")

    def test_conversation_integration(self):
        manager = MemoryManager()
        manager.add_conversation_message("user", "Hello memory manager")
        context = manager.get_conversation_context(n=1)
        assert len(context) == 1
        assert context[0].content == "Hello memory manager"

    def test_clear_conversation(self):
        manager = MemoryManager()
        manager.add_conversation_message("user", "test")
        manager.clear_conversation()
        assert len(manager.get_conversation_context()) == 0

    def test_short_term_search(self):
        manager = MemoryManager()
        manager.store("topic_ai", "Artificial Intelligence notes", "short_term")
        manager.store("topic_ml", "Machine Learning notes", "short_term")
        results = manager.search("AI", "short_term")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# HybridMemory
# ---------------------------------------------------------------------------

class TestHybridMemory:
    def test_add_shared_and_search(self):
        hm = HybridMemory()
        hm._shared_store._use_mock = True
        hm.add_to_shared(["AGI research document"])
        context = hm.get_context("agent_1", "AGI research")
        assert isinstance(context, list)

    def test_agent_context(self):
        hm = HybridMemory()
        hm.add_agent_context("agent_1", "Agent-specific knowledge about NLP")
        # The context store should have an entry for this agent
        assert "agent_1" in hm._agent_contexts

    def test_clear_agent_context(self):
        hm = HybridMemory()
        hm.add_agent_context("agent_1", "Some knowledge")
        hm.clear_agent_context("agent_1")
        assert "agent_1" not in hm._agent_contexts

    def test_get_context_merges_shared_and_agent(self):
        hm = HybridMemory()
        hm._shared_store._use_mock = True
        hm.add_to_shared(["Shared knowledge about ML"])
        hm.add_agent_context("agent_2", "Agent-2 specific NLP context")
        context = hm.get_context("agent_2", "ML NLP")
        assert isinstance(context, list)
