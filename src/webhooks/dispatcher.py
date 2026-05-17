from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds; doubles each retry


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
            "last_error": None,
            "delivery_count": 0,
            "failure_count": 0,
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
        await asyncio.gather(
            *[self._deliver(webhook, body) for webhook in targets],
            return_exceptions=True,
        )

    async def _deliver(self, webhook: Dict[str, Any], body: Dict[str, Any]) -> None:
        delay = _BASE_DELAY
        last_exc: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    resp = await client.post(webhook["url"], json=body)
                    resp.raise_for_status()
                    webhook["delivery_count"] = webhook.get("delivery_count", 0) + 1
                    webhook["last_error"] = None
                    logger.debug(
                        "Webhook delivered (id=%s event=%s attempt=%d status=%d)",
                        webhook["id"], body.get("event"), attempt, resp.status_code,
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    logger.warning(
                        "Webhook delivery attempt %d/%d failed (id=%s url=%s): %s",
                        attempt, _MAX_RETRIES, webhook["id"], webhook["url"], exc,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(delay)
                        delay *= 2
        webhook["failure_count"] = webhook.get("failure_count", 0) + 1
        webhook["last_error"] = str(last_exc)
        logger.error(
            "Webhook delivery permanently failed after %d attempts (id=%s url=%s)",
            _MAX_RETRIES, webhook["id"], webhook["url"],
        )
