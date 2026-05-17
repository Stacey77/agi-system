"""LLM token usage tracking — accumulates per-agent and per-task counts."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Approximate cost per 1K tokens (USD) — update as pricing changes
_COST_PER_1K: Dict[str, Dict[str, float]] = {
    "gpt-4o":         {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini":    {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo":    {"input": 0.010, "output": 0.030},
    "claude-opus-4-7":        {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-6":    {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001":    {"input": 0.00025, "output": 0.00125},
}


@dataclass
class UsageRecord:
    agent_name: str
    task_id: Optional[str]
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        costs = _COST_PER_1K.get(self.model, {"input": 0.002, "output": 0.002})
        return (self.input_tokens * costs["input"] + self.output_tokens * costs["output"]) / 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "timestamp": self.timestamp,
        }


class TokenTracker:
    """Thread-safe in-memory token usage store."""

    def __init__(self, max_records: int = 10_000) -> None:
        self._records: List[UsageRecord] = []
        self._lock = threading.Lock()
        self._max_records = max_records

    def record(
        self,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        task_id: Optional[str] = None,
    ) -> UsageRecord:
        r = UsageRecord(
            agent_name=agent_name,
            task_id=task_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        with self._lock:
            self._records.append(r)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records :]
        logger.debug(
            "Token usage: agent=%s model=%s in=%d out=%d cost=$%.5f",
            agent_name, model, input_tokens, output_tokens, r.estimated_cost_usd,
        )
        return r

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)
        by_agent: Dict[str, Dict[str, Any]] = {}
        total_input = total_output = 0.0
        total_cost = 0.0
        for r in records:
            agg = by_agent.setdefault(r.agent_name, {
                "input_tokens": 0, "output_tokens": 0,
                "total_tokens": 0, "estimated_cost_usd": 0.0, "calls": 0,
            })
            agg["input_tokens"] += r.input_tokens
            agg["output_tokens"] += r.output_tokens
            agg["total_tokens"] += r.total_tokens
            agg["estimated_cost_usd"] = round(agg["estimated_cost_usd"] + r.estimated_cost_usd, 6)
            agg["calls"] += 1
            total_input += r.input_tokens
            total_output += r.output_tokens
            total_cost += r.estimated_cost_usd
        return {
            "total_input_tokens": int(total_input),
            "total_output_tokens": int(total_output),
            "total_tokens": int(total_input + total_output),
            "total_estimated_cost_usd": round(total_cost, 6),
            "total_calls": len(records),
            "by_agent": by_agent,
        }

    def records_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._records if r.task_id == task_id]
