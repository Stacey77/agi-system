from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    def __init__(self) -> None:
        self._webhooks: Dict[str, Dict[str, Any]] = {}

    def register(self, url: str, events: List[str]) -> str:
        webhook_id = str(uuid.uuid4())
        self._webhooks[webhook_id] = {
            "id": webhook_id,
            "url": url,
            "events": events,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return webhook_id

    def unregister(self, webhook_id: str) -> bool:
        if webhook_id not in self._webhooks:
            return False
        del self._webhooks[webhook_id]
        return True

    def list_webhooks(self) -> List[Dict[str, Any]]:
        return list(self._webhooks.values())

    async def dispatch(self, event: str, payload: Dict[str, Any]) -> None:
        targets = [w for w in self._webhooks.values() if event in w["events"]]
        if not targets:
            return
        body = {"event": event, "payload": payload}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for webhook in targets:
                try:
                    await client.post(webhook["url"], json=body)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Webhook delivery failed (id=%s url=%s): %s",
                        webhook["id"],
                        webhook["url"],
                        exc,
                    )
