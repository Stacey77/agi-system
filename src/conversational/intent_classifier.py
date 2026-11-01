"""Lightweight intent classifier for conversational routing."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


class IntentClassifier:
    """Classifies user messages into intents and suggests the best agent."""

    INTENTS = [
        "question",
        "command",
        "task_request",
        "feedback",
        "greeting",
        "farewell",
        "clarification",
        "complaint",
        "general",
    ]

    _INTENT_TO_AGENT: Dict[str, str] = {
        "task_request": "planning_agent",
        "question": "research_agent",
        "command": "execution_agent",
        "feedback": "review_agent",
        "greeting": "kally_agent",
        "farewell": "kally_agent",
        "clarification": "planning_agent",
        "complaint": "kally_agent",
        "general": "kally_agent",
    }

    _GREETING_WORDS = {"hello", "hi", "hey", "howdy", "greetings", "good morning", "good afternoon", "good evening"}
    _FAREWELL_WORDS = {"bye", "goodbye", "see you", "farewell", "later", "take care", "ciao", "adios"}
    _QUESTION_WORDS = {"what", "who", "when", "where", "why", "how", "which", "is", "are", "was", "were", "do", "does", "did", "can", "could", "would", "should"}
    _TASK_WORDS = {"task", "do", "create", "build", "make", "generate", "write", "draft", "run", "execute", "analyse", "analyze", "summarize", "summarise", "research", "find", "search", "schedule", "deploy", "implement", "develop", "design"}
    _COMMAND_WORDS = {"start", "stop", "restart", "kill", "launch", "open", "close", "delete", "remove", "install", "uninstall", "enable", "disable", "set", "configure"}
    _FEEDBACK_WORDS = {"good", "bad", "great", "terrible", "awesome", "poor", "improve", "better", "worse", "feedback", "rating", "score", "review"}
    _COMPLAINT_WORDS = {"error", "broken", "doesn't work", "not working", "bug", "issue", "problem", "wrong", "fail", "failed", "crash"}
    _CLARIFICATION_WORDS = {"clarify", "explain", "what do you mean", "unclear", "confusing", "elaborate", "more detail"}

    def __init__(self, llm: Optional[Any] = None) -> None:
        self._llm = llm

    async def classify(
        self, text: str, context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        if self._llm is not None:
            try:
                return await self._llm_classify(text, context)
            except Exception:
                pass
        return self._heuristic_classify(text)

    async def _llm_classify(
        self, text: str, context: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        prompt = (
            "Classify the following user message into one of these intents: "
            + ", ".join(self.INTENTS)
            + ".\nRespond ONLY with valid JSON matching this schema: "
            '{"intent": "<intent>", "confidence": 0.0-1.0, "entities": [], "suggested_agent": "<agent>"}\n\n'
            f"Message: {text}"
        )
        response = await self._llm.agenerate([[{"role": "user", "content": prompt}]])
        raw = response.generations[0][0].text.strip()
        data = json.loads(raw)
        intent = data.get("intent", "general")
        return {
            "intent": intent,
            "confidence": float(data.get("confidence", 0.8)),
            "entities": data.get("entities", []),
            "suggested_agent": data.get(
                "suggested_agent", self._INTENT_TO_AGENT.get(intent, "kally_agent")
            ),
        }

    def _heuristic_classify(self, text: str) -> Dict[str, Any]:
        lower = text.lower().strip()
        tokens = set(re.findall(r"\w+", lower))

        # farewell
        if any(fw in lower for fw in self._FAREWELL_WORDS):
            return self._result("farewell", 0.9, lower)

        # greeting
        if any(gw in lower for gw in self._GREETING_WORDS) and len(lower) < 30:
            return self._result("greeting", 0.9, lower)

        # complaint
        if any(cw in lower for cw in self._COMPLAINT_WORDS):
            return self._result("complaint", 0.75, lower)

        # clarification
        if any(cw in lower for cw in self._CLARIFICATION_WORDS):
            return self._result("clarification", 0.75, lower)

        # feedback
        if any(fw in lower for fw in self._FEEDBACK_WORDS):
            return self._result("feedback", 0.7, lower)

        # task request
        if tokens & self._TASK_WORDS:
            return self._result("task_request", 0.8, lower)

        # command
        if tokens & self._COMMAND_WORDS:
            return self._result("command", 0.75, lower)

        # question
        first_token = lower.split()[0] if lower.split() else ""
        if lower.endswith("?") or first_token in self._QUESTION_WORDS:
            return self._result("question", 0.8, lower)

        return self._result("general", 0.5, lower)

    def _result(self, intent: str, confidence: float, text: str) -> Dict[str, Any]:
        entities = self._extract_entities(text)
        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "suggested_agent": self._INTENT_TO_AGENT.get(intent, "kally_agent"),
        }

    def _extract_entities(self, text: str) -> List[str]:
        # Very lightweight: extract capitalised multi-word phrases and quoted strings
        entities: List[str] = []
        quoted = re.findall(r'"([^"]+)"', text)
        entities.extend(quoted)
        caps = re.findall(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*\b", text)
        entities.extend(caps)
        return list(dict.fromkeys(entities))[:10]

    def __repr__(self) -> str:
        return f"IntentClassifier(llm={'set' if self._llm else 'none'})"
