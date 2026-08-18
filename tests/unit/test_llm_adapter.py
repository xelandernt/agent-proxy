from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from proxy.llm.adapter import LiteLLMResponsesAdapter, LLMUpstreamError
from proxy.model_deployments.schemas import ResolvedModelDeployment


def deployment() -> ResolvedModelDeployment:
    return ResolvedModelDeployment(
        name="public-model",
        upstream_model="anthropic/private-model",
        api_base="https://provider.example/v1",
        settings={"timeout": 42},
        secrets={"api_key": "provider-secret"},
    )


@pytest.mark.asyncio
async def test_adapter_owns_model_endpoint_credentials_and_stream_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_aresponses(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "id": "resp_1",
            "object": "response",
            "model": "anthropic/private-model",
            "_hidden_params": {"response_cost": 1},
        }

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    response = await LiteLLMResponsesAdapter().create(
        deployment(), {"input": "hello", "model": "attacker", "stream": True}
    )

    assert captured == {
        "timeout": 42,
        "api_key": "provider-secret",
        "input": "hello",
        "model": "anthropic/private-model",
        "stream": False,
        "api_base": "https://provider.example/v1",
    }
    assert response["model"] == "public-model"
    assert "_hidden_params" not in response


@pytest.mark.asyncio
async def test_adapter_streams_events_without_buffering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def events() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "response.created", "response": {"model": "private"}}
        yield {"type": "response.output_text.delta", "delta": "hello"}

    async def fake_aresponses(**_kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        return events()

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    stream = LiteLLMResponsesAdapter().stream(deployment(), {"input": "hello"})

    first = await anext(stream)
    assert first["type"] == "response.created"
    assert first["response"]["model"] == "public-model"
    second = await anext(stream)
    assert second["delta"] == "hello"


@pytest.mark.asyncio
async def test_adapter_closes_upstream_when_consumer_disconnects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    async def events() -> AsyncIterator[dict[str, Any]]:
        nonlocal closed
        try:
            yield {"type": "response.output_text.delta", "delta": "first"}
            yield {"type": "response.output_text.delta", "delta": "second"}
        finally:
            closed = True

    async def fake_aresponses(**_kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        return events()

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)
    stream = LiteLLMResponsesAdapter().stream(deployment(), {"input": "hello"})

    assert (await anext(stream))["delta"] == "first"
    await stream.aclose()

    assert closed is True


@pytest.mark.asyncio
async def test_adapter_sanitizes_upstream_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ProviderFailure(Exception):
        status_code = 429

    async def fake_aresponses(**_kwargs: Any) -> None:
        raise ProviderFailure("provider-secret https://internal.example")

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    with pytest.raises(LLMUpstreamError) as captured:
        await LiteLLMResponsesAdapter().create(deployment(), {"input": "hello"})

    assert captured.value.status_code == 429
    assert str(captured.value) == "The upstream model request failed."
    assert "provider-secret" not in str(captured.value)


@pytest.mark.asyncio
async def test_adapter_sanitizes_invalid_upstream_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_aresponses(**_kwargs: Any) -> object:
        return object()

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    with pytest.raises(LLMUpstreamError) as captured:
        await LiteLLMResponsesAdapter().create(deployment(), {"input": "hello"})

    assert captured.value.error_type == "InvalidLLMResponse"
