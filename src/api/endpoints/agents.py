"""Agent management endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents.base_agent import AgentConfig, AgentType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Built-in agents that cannot be removed at runtime
_PROTECTED_AGENTS = {"planning_agent", "execution_agent"}


class TaskRequest(BaseModel):
    task: str
    parameters: Dict[str, Any] = {}


class AgentCreateRequest(BaseModel):
    name: str
    agent_type: str  # must match AgentType enum values
    description: str = ""
    capabilities: List[str] = []
    tools: List[str] = []
    max_retries: int = 2
    temperature: float = 0.7


@router.get("/")
async def list_agents(request: Request) -> List[Dict[str, Any]]:
    """List all registered agents with name, type, and status."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        return []
    agents = factory.list_agents()
    return [
        {
            "name": name,
            "type": agent.config.agent_type,
            "status": "ready",
            "capabilities": agent.config.capabilities,
        }
        for name, agent in agents.items()
    ]


@router.post("/", status_code=201)
async def register_agent(body: AgentCreateRequest, request: Request) -> Dict[str, Any]:
    """Register a new agent at runtime."""
    # Validate agent_type against AgentType enum
    try:
        agent_type = AgentType(body.agent_type)
    except ValueError:
        valid = [t.value for t in AgentType]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid agent_type '{body.agent_type}'. Valid values: {valid}",
        )

    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    # Check for duplicate name
    if factory.get_agent(body.name) is not None:
        raise HTTPException(status_code=409, detail=f"Agent '{body.name}' is already registered")

    config = AgentConfig(
        name=body.name,
        agent_type=agent_type,
        description=body.description,
        capabilities=body.capabilities,
        tools=body.tools,
        max_retries=body.max_retries,
        temperature=body.temperature,
    )
    agent = factory.create_agent(config)

    # Wire token tracker if available and supported
    tracker = getattr(request.app.state, "token_tracker", None)
    if tracker is not None and hasattr(agent, "set_token_tracker"):
        agent.set_token_tracker(tracker)

    return agent.get_status()


@router.post("/{agent_name}/execute")
async def execute_agent_task(
    agent_name: str, body: TaskRequest, request: Request
) -> Dict[str, Any]:
    """Execute a task using the named agent."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    task_dict = {"task": body.task, **body.parameters}
    try:
        result = await agent.process_task(task_dict)
        return {"agent": agent_name, "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.error("Agent '%s' execution error: %s", agent_name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{agent_name}/stream")
async def stream_agent_task(
    agent_name: str, body: TaskRequest, request: Request
) -> StreamingResponse:
    """Stream agent output token-by-token via Server-Sent Events."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    task_dict = {"task": body.task, **body.parameters}

    async def _event_generator():
        try:
            async for chunk in agent.stream_task(task_dict):
                safe_chunk = chunk.replace("\n", "\\n")
                yield f"data: {safe_chunk}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.error("Agent '%s' stream error: %s", agent_name, exc)
            yield f"data: {{'error': '{exc}'}}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.websocket("/{agent_name}/ws")
async def websocket_agent_task(agent_name: str, websocket: WebSocket) -> None:
    """Stream agent output over a WebSocket connection.

    The client sends a JSON object ``{"task": "...", "parameters": {...}}``
    and receives text chunks followed by a final ``[DONE]`` message.
    """
    factory = getattr(websocket.app.state, "agent_factory", None)
    agent = factory.get_agent(agent_name) if factory else None

    await websocket.accept()

    if agent is None:
        await websocket.send_json({"error": f"Agent '{agent_name}' not found"})
        await websocket.close(code=1008)
        return

    try:
        data = await websocket.receive_json()
        task_dict = {"task": data.get("task", ""), **data.get("parameters", {})}
        async for chunk in agent.stream_task(task_dict):
            await websocket.send_text(chunk)
        await websocket.send_text("[DONE]")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from agent '%s'", agent_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("WebSocket error for agent '%s': %s", agent_name, exc)
        try:
            await websocket.send_json({"error": str(exc)})
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


@router.get("/{agent_name}/memory")
async def agent_memory_recall(
    agent_name: str, query: str, request: Request, k: int = 3
) -> Dict[str, Any]:
    """Recall past tasks similar to *query* from the agent's persistent memory."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    recalled = agent.recall_similar_tasks(query, k=k)
    return {"agent": agent_name, "query": query, "results": recalled}


@router.get("/{agent_name}/status")
async def agent_status(agent_name: str, request: Request) -> Dict[str, Any]:
    """Get status and memory usage for the named agent."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    return agent.get_status()


@router.post("/{agent_name}/circuit/reset")
async def reset_circuit_breaker(agent_name: str, request: Request) -> Dict[str, Any]:
    """Reset an agent's circuit breaker — use after fixing the underlying issue."""
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    agent._consecutive_failures = 0
    agent._circuit_open_until = 0.0
    return {"agent": agent_name, "circuit_reset": True, "status": agent.get_status()}


@router.get("/{agent_name}/history")
async def agent_token_history(
    agent_name: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Return paginated token-usage history for the named agent (newest first).

    Each record contains the task_id, model, input/output token counts, and
    timestamp of a single LLM call made by this agent.
    """
    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    if factory.get_agent(agent_name) is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    tracker = getattr(request.app.state, "token_tracker", None)
    if tracker is None:
        return {
            "agent_name": agent_name,
            "total_calls": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "records": [],
        }

    # Pull per-agent aggregate from summary
    summary = tracker.summary()
    agg = summary.get("by_agent", {}).get(agent_name, {})

    # Filter raw records by agent_name, then return newest-first with pagination
    with tracker._lock:
        agent_records = [r for r in tracker._records if r.agent_name == agent_name]

    agent_records_newest_first = list(reversed(agent_records))
    page = agent_records_newest_first[offset: offset + limit]

    return {
        "agent_name": agent_name,
        "total_calls": agg.get("calls", 0),
        "total_tokens": agg.get("total_tokens", 0),
        "estimated_cost_usd": agg.get("estimated_cost_usd", 0.0),
        "records": [
            {
                "task_id": r.task_id,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "timestamp": r.timestamp,
            }
            for r in page
        ],
    }


@router.delete("/{agent_name}", status_code=204)
async def deregister_agent(agent_name: str, request: Request) -> None:
    """Remove a runtime-registered agent. Built-in agents cannot be removed."""
    if agent_name in _PROTECTED_AGENTS:
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{agent_name}' is a built-in agent and cannot be deleted",
        )

    factory = getattr(request.app.state, "agent_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    if factory.get_agent(agent_name) is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    if hasattr(factory, "remove_agent"):
        factory.remove_agent(agent_name)
    else:
        del factory._agents[agent_name]
