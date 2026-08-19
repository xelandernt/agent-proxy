from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.app.model_usage.recorder import ModelUsageRecord, ModelUsageRecorder

KEY_ID = UUID("4fb9ca09-2e2b-4e3f-ac94-630f911c8acf")
USER_ID = UUID("c8464904-f61b-48e3-9e87-ef0a1e15a05e")


def usage_record() -> ModelUsageRecord:
    return ModelUsageRecord(
        user_id=USER_ID,
        api_key_id=KEY_ID,
        model_name="alpha",
        provider="anthropic",
        status_code=200,
        input_tokens=2,
        output_tokens=3,
        total_tokens=5,
        cached_tokens=1,
        cost_usd=Decimal("0.00125"),
        duration_ms=10,
        error_type=None,
        streaming=False,
        ts=datetime.now(UTC),
    )


class CapturingRecorder(ModelUsageRecorder):
    def __init__(self, **kwargs: object) -> None:
        factory = cast(async_sessionmaker, object())
        super().__init__(factory, **kwargs)  # type: ignore[arg-type]
        self.persisted: list[ModelUsageRecord] = []

    async def _persist(self, records: list[ModelUsageRecord]) -> None:
        self.persisted.extend(records)


async def test_usage_queue_is_bounded_and_flushes_accepted_events() -> None:
    recorder = CapturingRecorder(queue_size=1)
    recorder.record(usage_record())
    recorder.record(usage_record())

    await recorder.start()
    await recorder.stop()

    assert recorder.dropped_events == 1
    assert len(recorder.persisted) == 1


async def test_usage_shutdown_has_a_bounded_flush_timeout() -> None:
    class BlockingRecorder(CapturingRecorder):
        async def _persist(self, records: list[ModelUsageRecord]) -> None:
            await asyncio.Event().wait()

    recorder = BlockingRecorder(flush_timeout_seconds=0.01)
    await recorder.start()
    recorder.record(usage_record())
    await asyncio.sleep(0)

    await asyncio.wait_for(recorder.stop(), timeout=0.5)
