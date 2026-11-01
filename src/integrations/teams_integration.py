"""Microsoft Teams integration via Incoming Webhooks."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False


class TeamsIntegration:
    """Async Teams client using Incoming Webhook connectors."""

    def __init__(self, webhook_url: str = "") -> None:
        self._webhook = webhook_url

    async def send_message(self, text: str, title: Optional[str] = None) -> bool:
        if not _HTTPX or not self._webhook:
            return False
        payload: Dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "text": text,
        }
        if title:
            payload["title"] = title
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self._webhook,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=10,
            )
        return r.status_code in (200, 202)

    async def send_adaptive_card(self, card: Dict[str, Any]) -> bool:
        if not _HTTPX or not self._webhook:
            return False
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self._webhook,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=10,
            )
        return r.status_code in (200, 202)

    async def send_fact_set(
        self, title: str, facts: List[Dict[str, str]], text: str = ""
    ) -> bool:
        card: Dict[str, Any] = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [{"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium"}],
        }
        if text:
            card["body"].append({"type": "TextBlock", "text": text, "wrap": True})
        card["body"].append(
            {"type": "FactSet", "facts": [{"title": f["title"], "value": f["value"]} for f in facts]}
        )
        return await self.send_adaptive_card(card)

    def __repr__(self) -> str:
        return f"TeamsIntegration(webhook={'set' if self._webhook else 'none'})"
