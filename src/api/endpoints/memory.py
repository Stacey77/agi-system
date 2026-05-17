"""Memory REST API — exposes MemoryManager and HybridMemory over HTTP."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class StoreRequest(BaseModel):
    key: str
    value: str
    memory_type: str = "short_term"


class ConversationMessageRequest(BaseModel):
    role: str
    content: str


class HybridContextRequest(BaseModel):
    agent_id: str
    query: str
    k: int = 5


class HybridStoreRequest(BaseModel):
    documents: List[str]
    agent_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_memory_manager(request: Request):
    mm = getattr(request.app.state, "memory_manager", None)
    if mm is None:
        raise HTTPException(status_code=503, detail="Memory manager not initialised")
    return mm


def _get_hybrid_memory(request: Request):
    hm = getattr(request.app.state, "hybrid_memory", None)
    if hm is None:
        raise HTTPException(status_code=503, detail="Hybrid memory not initialised")
    return hm


# ---------------------------------------------------------------------------
# Short-term memory
# ---------------------------------------------------------------------------


@router.get("/short-term")
async def list_short_term(request: Request) -> Dict[str, Any]:
    """Return all keys and values stored in short-term memory."""
    mm = _get_memory_manager(request)
    return {"memory": mm._short_term}


@router.delete("/short-term")
async def clear_short_term(request: Request) -> Dict[str, str]:
    """Clear all short-term memory entries."""
    mm = _get_memory_manager(request)
    mm._short_term.clear()
    return {"message": "Short-term memory cleared"}


@router.delete("/short-term/{key}")
async def delete_short_term_key(key: str, request: Request) -> Dict[str, str]:
    """Delete a single key from short-term memory."""
    mm = _get_memory_manager(request)
    if key not in mm._short_term:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found in short-term memory")
    del mm._short_term[key]
    return {"message": f"Key '{key}' deleted from short-term memory"}


# ---------------------------------------------------------------------------
# Generic store / retrieve / search
# ---------------------------------------------------------------------------


@router.post("/store")
async def store_memory(body: StoreRequest, request: Request) -> Dict[str, str]:
    """Store a value in the specified memory type."""
    mm = _get_memory_manager(request)
    try:
        mm.store(body.key, body.value, body.memory_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"message": f"Stored key '{body.key}' in '{body.memory_type}' memory"}


@router.get("/retrieve")
async def retrieve_memory(
    request: Request,
    key: str,
    memory_type: str = "short_term",
) -> Dict[str, Any]:
    """Retrieve a value by key from the specified memory type."""
    mm = _get_memory_manager(request)
    try:
        value = mm.retrieve(key, memory_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"key": key, "memory_type": memory_type, "value": value}


@router.get("/search")
async def search_memory(
    request: Request,
    query: str,
    memory_type: str = "long_term",
) -> Dict[str, Any]:
    """Semantic search across the specified memory type."""
    mm = _get_memory_manager(request)
    try:
        results = mm.search(query, memory_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"query": query, "memory_type": memory_type, "results": results}


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------


@router.get("/conversation")
async def get_conversation(request: Request, n: int = 10) -> Dict[str, Any]:
    """Return the last *n* conversation messages."""
    mm = _get_memory_manager(request)
    context = mm.get_conversation_context(n)
    return {"context": context, "count": len(context)}


@router.post("/conversation")
async def add_conversation_message(
    body: ConversationMessageRequest, request: Request
) -> Dict[str, str]:
    """Append a message to the conversation history."""
    mm = _get_memory_manager(request)
    mm.add_conversation_message(body.role, body.content)
    return {"message": "Conversation message added"}


@router.delete("/conversation")
async def clear_conversation(request: Request) -> Dict[str, str]:
    """Clear all conversation history."""
    mm = _get_memory_manager(request)
    mm.clear_conversation()
    return {"message": "Conversation history cleared"}


# ---------------------------------------------------------------------------
# Hybrid memory
# ---------------------------------------------------------------------------


@router.post("/hybrid/context")
async def hybrid_get_context(
    body: HybridContextRequest, request: Request
) -> Dict[str, Any]:
    """Retrieve merged context for an agent from hybrid memory."""
    hm = _get_hybrid_memory(request)
    try:
        context = hm.get_context(body.agent_id, body.query, k=body.k)
    except Exception as exc:  # noqa: BLE001
        logger.error("HybridMemory.get_context error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"agent_id": body.agent_id, "query": body.query, "context": context}


@router.post("/hybrid/store")
async def hybrid_store(body: HybridStoreRequest, request: Request) -> Dict[str, str]:
    """Store documents in hybrid memory — agent-specific or shared."""
    hm = _get_hybrid_memory(request)
    try:
        if body.agent_id is not None:
            for doc in body.documents:
                hm.add_agent_context(body.agent_id, doc)
            return {"message": f"Stored {len(body.documents)} document(s) for agent '{body.agent_id}'"}
        hm.add_to_shared(body.documents)
        return {"message": f"Stored {len(body.documents)} document(s) in shared hybrid memory"}
    except Exception as exc:  # noqa: BLE001
        logger.error("HybridMemory store error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/hybrid/{agent_id}")
async def hybrid_clear_agent(agent_id: str, request: Request) -> Dict[str, str]:
    """Clear all hybrid memory context for the given agent."""
    hm = _get_hybrid_memory(request)
    hm.clear_agent_context(agent_id)
    return {"message": f"Hybrid memory cleared for agent '{agent_id}'"}
