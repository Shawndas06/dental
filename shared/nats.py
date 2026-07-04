from __future__ import annotations

import json
import logging

from shared.events import STREAMS, EventEnvelope

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, nats_url: str, enabled: bool = True) -> None:
        self.nats_url = nats_url
        self.enabled = enabled
        self.published: list[tuple[str, EventEnvelope]] = []
        self._client: NATS | None = None

    async def connect(self) -> None:
        if not self.enabled or self._client:
            return
        try:
            from nats.aio.client import Client as NATS
        except ModuleNotFoundError:
            logger.warning("nats-py is not installed; publisher stays in memory mode")
            self.enabled = False
            return
        self._client = NATS()
        await self._client.connect(self.nats_url)
        js = self._client.jetstream()
        for stream, subjects in STREAMS.items():
            try:
                await js.add_stream(name=stream, subjects=subjects)
            except Exception as exc:  # Stream may already exist.
                logger.debug("NATS stream init skipped for %s: %s", stream, exc)

    async def publish(self, subject: str, event: EventEnvelope) -> None:
        self.published.append((subject, event))
        if not self.enabled:
            return
        try:
            await self.connect()
            assert self._client is not None
            payload = event.model_dump_json().encode("utf-8")
            await self._client.jetstream().publish(subject, payload)
        except Exception as exc:
            logger.warning("NATS publish failed for %s: %s", subject, exc)

    async def close(self) -> None:
        if self._client:
            await self._client.drain()
            self._client = None


def decode_event(data: bytes) -> EventEnvelope:
    return EventEnvelope.model_validate(json.loads(data.decode("utf-8")))
