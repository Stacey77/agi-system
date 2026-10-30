"""Per-session sliding context window tracker."""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional


class ContextTracker:
    """In-memory sliding context window with optional LLM-based summarisation."""

    def __init__(self, max_messages: int = 20, max_tokens: int = 8000) -> None:
        self._max_messages = max_messages
        self._max_tokens = max_tokens
        self._sessions: Dict[str, Deque[Dict[str, str]]] = {}

    def _get_or_create(self, session_id: str) -> Deque[Dict[str, str]]:
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self._max_messages)
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        dq = self._get_or_create(session_id)
        dq.append({"role": role, "content": content})

    def get_context(self, session_id: str) -> List[Dict[str, str]]:
        return list(self._sessions.get(session_id, deque()))

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _approximate_tokens(self, session_id: str) -> int:
        return sum(
            len(m.get("content", "")) // 4 + 1
            for m in self._sessions.get(session_id, [])
        )

    async def summarize_if_needed(
        self, session_id: str, llm: Optional[Any] = None
    ) -> bool:
        dq = self._sessions.get(session_id)
        if dq is None:
            return False
        token_count = self._approximate_tokens(session_id)
        if len(dq) < self._max_messages and token_count < self._max_tokens:
            return False
        if llm is None:
            # Hard truncate oldest half without summarisation
            msgs = list(dq)
            keep = msgs[len(msgs) // 2 :]
            self._sessions[session_id] = deque(keep, maxlen=self._max_messages)
            return False

        msgs = list(dq)
        half = len(msgs) // 2
        to_summarize = msgs[:half]
        to_keep = msgs[half:]

        summary_prompt = (
            "Summarise the following conversation excerpt in 2-3 sentences for context:\n\n"
            + "\n".join(f"{m['role']}: {m['content']}" for m in to_summarize)
        )
        try:
            resp = await llm.agenerate([[{"role": "user", "content": summary_prompt}]])
            summary_text = resp.generations[0][0].text.strip()
        except Exception:
            summary_text = "[Earlier conversation summarised]"

        new_dq: Deque[Dict[str, str]] = deque(maxlen=self._max_messages)
        new_dq.append({"role": "system", "content": f"Summary of earlier conversation: {summary_text}"})
        new_dq.extend(to_keep)
        self._sessions[session_id] = new_dq
        return True

    def session_count(self) -> int:
        return len(self._sessions)

    def __repr__(self) -> str:
        return (
            f"ContextTracker(max_messages={self._max_messages}, "
            f"max_tokens={self._max_tokens}, sessions={self.session_count()})"
        )
