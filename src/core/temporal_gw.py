"""Temporal is optional. If port 7233 is closed, workflows run in-process immediately."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from core.config import get_settings

_AVAILABLE: bool | None = None
_CHECKED_AT = 0.0
_TTL_DOWN = 20.0
_TTL_UP = 5.0
_CONNECT_TIMEOUT = 0.45


def temporal_available() -> bool:
    global _AVAILABLE, _CHECKED_AT
    now = time.monotonic()
    if _AVAILABLE is False and now - _CHECKED_AT < _TTL_DOWN:
        return False
    if _AVAILABLE is True and now - _CHECKED_AT < _TTL_UP:
        return True
    settings = get_settings()
    host, _, port = settings.temporal_address.partition(":")
    host = host or "127.0.0.1"
    port = int(port or 7233)
    try:
        import socket

        with socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT):
            _AVAILABLE = True
    except OSError:
        _AVAILABLE = False
    _CHECKED_AT = now
    return bool(_AVAILABLE)


async def start_on_temporal(workflow: str, payload: dict, workflow_id: str) -> dict:
    from temporalio.client import Client

    settings = get_settings()
    client = await asyncio.wait_for(Client.connect(settings.temporal_address), timeout=2.0)
    handle = await client.start_workflow(
        workflow,
        payload,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return {"workflow_id": handle.id, "run_id": handle.result_run_id, "started": True, "mode": "temporal"}


def dispatch(workflow: str, payload: dict, workflow_id: str | None, runner) -> dict:
    import uuid

    from core.errors import ProviderUnavailable
    from core.provider_plane import is_production

    workflow_id = workflow_id or f"{workflow}-{uuid.uuid4().hex[:10]}"
    if is_production() and not temporal_available():
        raise ProviderUnavailable("Temporal is required in production mode")
    if temporal_available():
        try:
            return asyncio.run(start_on_temporal(workflow, payload, workflow_id))
        except Exception as exc:
            if is_production():
                raise ProviderUnavailable(f"Temporal dispatch failed: {exc}") from exc
    result: Any = runner(workflow, payload)
    return {
        "workflow_id": workflow_id,
        "started": True,
        "mode": "in_process",
        "fallback": "sync",
        "result": result,
    }
