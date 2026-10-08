"""In-memory pub/sub per project, with a short replay buffer for SSE reconnects."""

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

REPLAY = 500


@dataclass(frozen=True)
class Event:
    id: int
    type: str
    data: dict[str, Any]


class Bus:
    def __init__(self) -> None:
        self._last_id = 0
        self._history: defaultdict[int, deque[Event]] = defaultdict(lambda: deque(maxlen=REPLAY))
        self._subscribers: defaultdict[int, set[asyncio.Queue[Event]]] = defaultdict(set)

    def publish(self, project_id: int, type: str, **data: Any) -> None:
        self._last_id += 1
        event = Event(self._last_id, type, data)
        self._history[project_id].append(event)
        for queue in self._subscribers[project_id]:
            queue.put_nowait(event)

    async def subscribe(self, project_id: int, after_id: int = 0) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers[project_id].add(queue)
        try:
            for event in list(self._history[project_id]):
                if event.id > after_id:
                    yield event
            while True:
                event = await queue.get()
                if event.id > after_id:
                    yield event
        finally:
            self._subscribers[project_id].discard(queue)


bus = Bus()
