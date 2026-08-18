from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.app.model_usage.models import ModelUsageEvent

logger = logging.getLogger(__name__)

MODEL_USAGE_QUEUE_SIZE = 4096
MODEL_USAGE_BATCH_SIZE = 100
MODEL_USAGE_FLUSH_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class ModelUsageRecord:
    user_id: uuid.UUID
    api_key_id: uuid.UUID
    model_name: str
    provider: str | None
    status_code: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: int
    error_type: str | None
    streaming: bool
    ts: datetime


class ModelUsageRecorder:
    """Bounded, lifecycle-owned model usage writer."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        queue_size: int = MODEL_USAGE_QUEUE_SIZE,
        batch_size: int = MODEL_USAGE_BATCH_SIZE,
        flush_timeout_seconds: float = MODEL_USAGE_FLUSH_TIMEOUT_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._queue: asyncio.Queue[ModelUsageRecord | None] = asyncio.Queue(queue_size)
        self._batch_size = batch_size
        self._flush_timeout_seconds = flush_timeout_seconds
        self._worker: asyncio.Task[None] | None = None
        self.dropped_events = 0

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    def record(self, record: ModelUsageRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            self.dropped_events += 1
            logger.warning(
                "Model usage queue is full; dropping event for '%s'.",
                record.model_name,
            )

    async def stop(self) -> None:
        if self._worker is None:
            return
        try:
            await asyncio.wait_for(
                self._queue.join(), timeout=self._flush_timeout_seconds
            )
            await self._queue.put(None)
            await asyncio.wait_for(self._worker, timeout=self._flush_timeout_seconds)
        except TimeoutError:
            logger.warning("Timed out while flushing model usage events.")
            self._worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker
        self._worker = None

    async def _run(self) -> None:
        while True:
            first = await self._queue.get()
            if first is None:
                self._queue.task_done()
                return
            batch = [first]
            while len(batch) < self._batch_size:
                try:
                    item = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item is None:
                    self._queue.task_done()
                    break
                batch.append(item)
            try:
                await self._persist(batch)
            finally:
                for _ in batch:
                    self._queue.task_done()

    async def _persist(self, records: list[ModelUsageRecord]) -> None:
        try:
            async with self._session_factory() as session:
                session.add_all(ModelUsageEvent(**asdict(record)) for record in records)
                await session.commit()
        except Exception:
            logger.exception("Failed to persist %d model usage events.", len(records))
