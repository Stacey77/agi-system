from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class WebhookRegistration(BaseModel):
    url: str
    events: List[str]


def _get_dispatcher(request: Request):
    dispatcher = getattr(request.app.state, "webhook_dispatcher", None)
    if dispatcher is None:
        raise HTTPException(status_code=503, detail="Webhook dispatcher not initialised")
    return dispatcher


@router.post("/", status_code=201)
async def register_webhook(body: WebhookRegistration, request: Request) -> Dict[str, Any]:
    dispatcher = _get_dispatcher(request)
    webhook_id = dispatcher.register(url=body.url, events=body.events)
    return {"webhook_id": webhook_id, "url": body.url, "events": body.events}


@router.delete("/{webhook_id}")
async def unregister_webhook(webhook_id: str, request: Request) -> Dict[str, str]:
    dispatcher = _get_dispatcher(request)
    removed = dispatcher.unregister(webhook_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")
    return {"message": f"Webhook '{webhook_id}' removed"}


@router.get("/")
async def list_webhooks(request: Request) -> List[Dict[str, Any]]:
    dispatcher = _get_dispatcher(request)
    return dispatcher.list_webhooks()


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str, request: Request) -> Dict[str, Any]:
    dispatcher = _get_dispatcher(request)
    webhooks = {w["id"]: w for w in dispatcher.list_webhooks()}
    if webhook_id not in webhooks:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")
    await dispatcher.dispatch(
        event="ping",
        payload={"message": "test ping", "webhook_id": webhook_id},
    )
    return {"message": "Test ping dispatched", "webhook_id": webhook_id}
