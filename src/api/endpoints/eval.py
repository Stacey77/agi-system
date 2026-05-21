from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])

_BENCHMARKS: Dict[str, List[str]] = {
    "standard": [
        "Summarise the following text: The quick brown fox jumps over the lazy dog",
        "What is 2 + 2?",
        "List three programming languages",
        "What is the capital of France?",
        "Write a one-sentence description of Python",
    ],
}


class EvalRequest(BaseModel):
    agent_name: str
    benchmark: str = "standard"
    tasks: Optional[List[str]] = None


def _get_factory(request: Request):
    return getattr(request.app.state, "agent_factory", None)


def _get_eval_results(request: Request) -> Dict[str, Any]:
    return getattr(request.app.state, "eval_results", {})


def _get_eval_store(request: Request):
    return getattr(request.app.state, "eval_store", None)


@router.post("/run")
async def run_evaluation(body: EvalRequest, request: Request) -> Dict[str, Any]:
    factory = _get_factory(request)
    if factory is None:
        raise HTTPException(status_code=503, detail="Agent system not initialised")

    agent = factory.get_agent(body.agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{body.agent_name}' not found")

    if body.tasks:
        tasks_to_run = body.tasks
    else:
        tasks_to_run = _BENCHMARKS.get(body.benchmark)
        if tasks_to_run is None:
            raise HTTPException(
                status_code=404, detail=f"Benchmark '{body.benchmark}' not found"
            )

    eval_id = str(uuid.uuid4())
    started = time.monotonic()
    task_results: List[Dict[str, Any]] = []

    for task_prompt in tasks_to_run:
        t0 = time.monotonic()
        try:
            result = await agent.process_task({"task": task_prompt})
            task_results.append(
                {
                    "task": task_prompt,
                    "status": "pass",
                    "score": 1.0,
                    "duration_s": round(time.monotonic() - t0, 3),
                    "output": result,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Eval task failed for agent '%s': %s", body.agent_name, exc)
            task_results.append(
                {
                    "task": task_prompt,
                    "status": "fail",
                    "score": 0.0,
                    "duration_s": round(time.monotonic() - t0, 3),
                    "error": str(exc),
                }
            )

    total_duration = round(time.monotonic() - started, 3)
    total_score = (
        sum(t["score"] for t in task_results) / len(task_results) if task_results else 0.0
    )

    eval_record: Dict[str, Any] = {
        "eval_id": eval_id,
        "agent": body.agent_name,
        "benchmark": body.benchmark,
        "score": round(total_score, 4),
        "tasks": task_results,
        "duration_s": total_duration,
    }

    eval_results = _get_eval_results(request)
    eval_results[eval_id] = eval_record

    store = _get_eval_store(request)
    if store is not None:
        store.save(eval_record)

    return eval_record


@router.get("/results")
async def list_eval_results(request: Request) -> List[Dict[str, Any]]:
    store = _get_eval_store(request)
    if store is not None:
        return store.load_all()
    return list(_get_eval_results(request).values())


@router.get("/results/{eval_id}")
async def get_eval_result(eval_id: str, request: Request) -> Dict[str, Any]:
    store = _get_eval_store(request)
    if store is not None:
        result = store.get(eval_id)
    else:
        result = _get_eval_results(request).get(eval_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Eval result '{eval_id}' not found")
    return result


@router.delete("/results/{eval_id}")
async def delete_eval_result(eval_id: str, request: Request) -> Dict[str, str]:
    store = _get_eval_store(request)
    deleted = False
    if store is not None:
        deleted = store.delete(eval_id)
    else:
        eval_results = _get_eval_results(request)
        if eval_id in eval_results:
            del eval_results[eval_id]
            deleted = True
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Eval result '{eval_id}' not found")
    return {"message": f"Eval result '{eval_id}' deleted"}


@router.get("/benchmarks")
async def list_benchmarks() -> Dict[str, Any]:
    return {
        "benchmarks": [
            {"name": name, "task_count": len(tasks)}
            for name, tasks in _BENCHMARKS.items()
        ]
    }
