"""Agent management endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class TaskRequest(BaseModel):
    task: str
    parameters: Dict[str, Any] = {}


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
