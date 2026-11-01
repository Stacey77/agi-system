"""Slack integration — webhook dispatch and event verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False


class SlackIntegration:
    """Async Slack integration using Incoming Webhooks and Web API."""

    def __init__(
        self,
        bot_token: str = "",
        signing_secret: str = "",
        webhook_url: str = "",
    ) -> None:
        self._token = bot_token
        self._secret = signing_secret
        self._webhook = webhook_url

    # --- Outbound ---

    async def post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not _HTTPX:
            return {"ok": False, "error": "httpx not installed"}
        payload: Dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=10,
            )
        return r.json()

    async def send_webhook(self, text: str, blocks: Optional[List[Dict]] = None) -> bool:
        if not _HTTPX or not self._webhook:
            return False
        payload: Dict[str, Any] = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient() as client:
            r = await client.post(
                self._webhook,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
                timeout=10,
            )
        return r.status_code == 200

    async def list_channels(self) -> List[Dict[str, Any]]:
        if not _HTTPX:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://slack.com/api/conversations.list",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10,
            )
        data = r.json()
        return data.get("channels", [])

    # --- Inbound verification ---

    def verify_signature(self, body: bytes, timestamp: str, signature: str) -> bool:
        if not self._secret:
            return True
        if abs(time.time() - float(timestamp)) > 300:
            return False
        base = f"v0:{timestamp}:{body.decode()}"
        expected = "v0=" + hmac.new(
            self._secret.encode(), base.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def __repr__(self) -> str:
        return f"SlackIntegration(token={'***' if self._token else 'none'})"
