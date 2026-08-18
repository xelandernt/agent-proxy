from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest

from proxy.api_keys.schemas import AuthenticatedApiKey
from proxy.app.inference.errors import OpenAIErrorException
from proxy.app.inference.schemas import ResponsesRequest
from proxy.app.inference.service import InferenceService
from proxy.app.model_usage.recorder import ModelUsageRecord
from proxy.llm.adapter import LLMUpstreamError
from proxy.model_deployments.schemas import ResolvedModelDeployment

KEY_ID = UUID("4fb9ca09-2e2b-4e3f-ac94-630f911c8acf")
USER_ID = UUID("c8464904-f61b-48e3-9e87-ef0a1e15a05e")


class FakeModels:
    def __init__(self) -> None:
        self.resolved: list[str] = []

    async def resolve(self, name: str) -> ResolvedModelDeployment:
        self.resolved.append(name)
        return ResolvedModelDeployment(
            name=name,
            upstream_model="anthropic/private",
            api_base=None,
            settings={},
            secrets={"api_key": "provider-secret"},
        )


class FakeAdapter:
    failure: LLMUpstreamError | None = None

    async def create(
        self,
        deployment: ResolvedModelDeployment,
        _request: dict[str, object],
    ) -> dict[str, Any]:
        if self.failure is not None:
            raise self.failure
        return {
            "id": "resp_1",
            "model": deployment.name,
            "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        }

    async def stream(
        self,
        deployment: ResolvedModelDeployment,
        _request: dict[str, object],
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "response.output_text.delta", "delta": "hello"}
        yield {
            "type": "response.completed",
            "response": {
                "model": deployment.name,
                "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
            },
        }


class FakeUsageRecorder:
    def __init__(self) -> None:
        self.records: list[ModelUsageRecord] = []

    def record(self, record: ModelUsageRecord) -> None:
        self.records.append(record)


def api_key(*models: str) -> AuthenticatedApiKey:
    return AuthenticatedApiKey(
        id=KEY_ID,
        user_id=USER_ID,
        models=frozenset(models),
    )


def service() -> tuple[InferenceService, FakeModels, FakeAdapter, FakeUsageRecorder]:
    models = FakeModels()
    adapter = FakeAdapter()
    usage = FakeUsageRecorder()
    inference = InferenceService(models, adapter, usage)  # type: ignore[arg-type]
    return inference, models, adapter, usage


@pytest.mark.asyncio
async def test_inference_conceals_models_outside_key_scope() -> None:
    inference, models, _, usage = service()

    with pytest.raises(OpenAIErrorException) as captured:
        await inference.create(
            api_key("alpha"),
            ResponsesRequest(model="beta", input="hello"),
        )

    assert captured.value.status_code == 404
    assert captured.value.body.code == "model_not_found"
    assert models.resolved == []
    assert usage.records[0].model_name == "beta"
    assert usage.records[0].status_code == 404


@pytest.mark.asyncio
async def test_inference_records_non_streaming_and_streaming_usage() -> None:
    inference, _, _, usage = service()
    request = ResponsesRequest(model="alpha", input="hello")

    response = await inference.create(api_key("alpha"), request)
    events = [event async for event in inference.stream(api_key("alpha"), request)]

    assert response["model"] == "alpha"
    assert events[-1]["type"] == "response.completed"
    assert [(record.streaming, record.total_tokens) for record in usage.records] == [
        (False, 8),
        (True, 8),
    ]
    assert all(record.provider == "anthropic" for record in usage.records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        (
            LLMUpstreamError(status_code=429, error_type="RateLimitError"),
            429,
            "upstream_rate_limit",
        ),
        (
            LLMUpstreamError(status_code=408, error_type="Timeout"),
            504,
            "upstream_timeout",
        ),
        (
            LLMUpstreamError(status_code=401, error_type="AuthenticationError"),
            502,
            "upstream_error",
        ),
    ],
)
async def test_inference_maps_upstream_failures_without_provider_details(
    failure: LLMUpstreamError,
    status_code: int,
    code: str,
) -> None:
    inference, _, adapter, usage = service()
    adapter.failure = failure

    with pytest.raises(OpenAIErrorException) as captured:
        await inference.create(
            api_key("alpha"),
            ResponsesRequest(model="alpha", input="hello"),
        )

    assert captured.value.status_code == status_code
    assert captured.value.body.code == code
    assert "provider-secret" not in captured.value.body.message
    assert usage.records[0].status_code == status_code
