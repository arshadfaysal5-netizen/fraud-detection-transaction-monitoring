import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.events import hub
from app.core.kafka import publish_event

router = APIRouter(tags=["stream"])


@router.get("/stream/alerts", summary="SSE stream of new alerts")
async def stream_alerts(request: Request):
    if not hub.available:
        async def empty():
            yield ": no-alert-hub\n\n"

        return StreamingResponse(empty(), media_type="text/event-stream")

    queue = hub.subscribe()

    async def event_stream():
        yield "event: connected\ndata: {}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15)
                yield f"event: alert\ndata: {payload}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/stream/test", summary="Push a test alert event (for exercising the UI)")
async def stream_test(payload: dict):
    publish_event("alerts", "test.event", "alert", None, payload)
    hub.publish({"type": "test", "payload": payload})
    return {"status": "ok"}