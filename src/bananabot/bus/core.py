"""Async message bus for decoupled communication."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

Handler = Callable[[Any], Coroutine[Any, Any, None]]

logger = logging.getLogger(__name__)


class MessageBus:
    """Async pub/sub message bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the message processing loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("MessageBus started")

    async def stop(self) -> None:
        """Stop the message processing loop."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MessageBus stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                topic, message = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                handlers = self._handlers.get(topic, [])
                if handlers:
                    await asyncio.gather(
                        *[h(message) for h in handlers],
                        return_exceptions=True,
                    )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"MessageBus error: {e}")

    def subscribe(self, topic: str, handler: Handler) -> None:
        """Subscribe to a topic."""
        self._handlers[topic].append(handler)
        logger.debug(f"Subscribed to {topic}")

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        """Unsubscribe from a topic."""
        if handler in self._handlers[topic]:
            self._handlers[topic].remove(handler)

    async def publish(self, topic: str, message: Any) -> None:
        """Publish a message to a topic."""
        await self._queue.put((topic, message))

    async def publish_sync(self, topic: str, message: Any) -> None:
        """Publish and wait for handlers to complete."""
        handlers = self._handlers.get(topic, [])
        if handlers:
            await asyncio.gather(*[h(message) for h in handlers], return_exceptions=True)
