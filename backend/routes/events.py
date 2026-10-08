import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from backend.events import Event, bus
from backend.redact import redact

router = APIRouter()


def sse(event: Event) -> str:
    return f"id: {event.id}\nevent: {event.type}\ndata: {redact(json.dumps(event.data))}\n\n"


@router.get("/api/events")
async def events(
    project_id: int, last_event_id: int = Header(default=0, alias="Last-Event-ID")
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        async for event in bus.subscribe(project_id, after_id=last_event_id):
            yield sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream")
