from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from litellm.types.llms.openai import ResponseCompletedEvent, ResponsesAPIResponse

from proxy.llm.adapter import LiteLLMResponsesAdapter, LLMUpstreamError
from proxy.model_deployments.schemas import ModelPricingView, ResolvedModelDeployment


def deployment() -> ResolvedModelDeployment:
    return ResolvedModelDeployment(
        name="public-model",
        upstream_model="anthropic/private-model",
        api_base="https://provider.example/v1",
        settings={"timeout": 42},
        secrets={"api_key": "provider-secret"},
        pricing=ModelPricingView(
            input_usd_per_million_tokens=Decimal(3),
            cached_input_usd_per_million_tokens=Decimal("0.3"),
            output_usd_per_million_tokens=Decimal(15),
            is_custom=False,
        ),
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

    result = await LiteLLMResponsesAdapter().create(
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
    assert result.payload["model"] == "public-model"
    assert "_hidden_params" not in result.payload
    assert result.accounting.cost_usd == Decimal(1)


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
    assert first.payload["type"] == "response.created"
    assert first.payload["response"]["model"] == "public-model"
    second = await anext(stream)
    assert second.payload["delta"] == "hello"


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

    assert (await anext(stream)).payload["delta"] == "first"
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


def response(*, cost: object = 0.00125) -> ResponsesAPIResponse:
    value = ResponsesAPIResponse(
        id="resp_1",
        created_at=1,
        model="anthropic/private-model",
        output=[],
        usage={
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
            "input_tokens_details": {"cached_tokens": 2},
        },
    )
    value._hidden_params["response_cost"] = cost
    return value


@pytest.mark.asyncio
async def test_adapter_extracts_typed_non_streaming_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_aresponses(**_kwargs: Any) -> ResponsesAPIResponse:
        return response(cost=0.00125)

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    result = await LiteLLMResponsesAdapter().create(deployment(), {"input": "hello"})

    assert result.accounting.input_tokens == 5
    assert result.accounting.output_tokens == 3
    assert result.accounting.total_tokens == 8
    assert result.accounting.cached_tokens == 2
    assert result.accounting.cost_usd == Decimal("0.00125")
    assert result.payload["model"] == "public-model"
    assert "_hidden_params" not in result.payload


@pytest.mark.asyncio
async def test_adapter_calculates_non_streaming_cost_when_provider_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = response(cost=None)
    upstream._hidden_params.clear()
    calls: list[object] = []

    async def fake_aresponses(**_kwargs: Any) -> ResponsesAPIResponse:
        return upstream

    def fake_completion_cost(*, completion_response: object) -> float:
        calls.append(completion_response)
        return 0.00125

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)
    monkeypatch.setattr(
        "proxy.llm.adapter.litellm.completion_cost", fake_completion_cost
    )

    result = await LiteLLMResponsesAdapter().create(deployment(), {"input": "hello"})

    assert result.accounting.cost_usd == Decimal("0.00125")
    assert calls == [upstream]


@pytest.mark.asyncio
async def test_adapter_calculates_terminal_stream_cost_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal_response = response(cost=None)
    terminal_response._hidden_params.clear()
    terminal = ResponseCompletedEvent(
        type="response.completed", response=terminal_response
    )
    calls: list[object] = []

    async def events() -> AsyncIterator[ResponseCompletedEvent]:
        yield terminal

    async def fake_aresponses(**_kwargs: Any) -> AsyncIterator[ResponseCompletedEvent]:
        return events()

    def fake_completion_cost(*, completion_response: object) -> float:
        calls.append(completion_response)
        return 0.00125

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)
    monkeypatch.setattr(
        "proxy.llm.adapter.litellm.completion_cost", fake_completion_cost
    )

    results = [
        result
        async for result in LiteLLMResponsesAdapter().stream(
            deployment(), {"input": "hello"}
        )
    ]

    assert results[0].accounting.total_tokens == 8
    assert results[0].accounting.cost_usd == Decimal("0.00125")
    assert calls == [terminal_response]
    assert "cost" not in results[0].payload["response"]["usage"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tokens", "cost"),
    [
        (-1, -1),
        (True, True),
        (1.5, float("inf")),
        ("1", float("nan")),
    ],
)
async def test_adapter_rejects_invalid_accounting_values(
    monkeypatch: pytest.MonkeyPatch,
    tokens: object,
    cost: object,
) -> None:
    raw = {
        "id": "resp_1",
        "model": "private",
        "usage": {
            "input_tokens": tokens,
            "output_tokens": tokens,
            "total_tokens": tokens,
        },
        "_hidden_params": {"response_cost": cost},
    }

    async def fake_aresponses(**_kwargs: Any) -> dict[str, Any]:
        return raw

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    result = await LiteLLMResponsesAdapter().create(deployment(), {"input": "hello"})

    assert result.accounting.input_tokens is None
    assert result.accounting.output_tokens is None
    assert result.accounting.total_tokens is None
    assert result.accounting.cost_usd is None


@pytest.mark.asyncio
async def test_adapter_preserves_zero_accounting_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = {
        "id": "resp_1",
        "model": "private",
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "_hidden_params": {"response_cost": 0.0},
    }

    async def fake_aresponses(**_kwargs: Any) -> dict[str, Any]:
        return raw

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    result = await LiteLLMResponsesAdapter().create(deployment(), {"input": "hello"})

    assert result.accounting.input_tokens == 0
    assert result.accounting.output_tokens == 0
    assert result.accounting.total_tokens == 0
    assert result.accounting.cost_usd == Decimal("0.0")


@pytest.mark.asyncio
async def test_adapter_custom_pricing_overrides_provider_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom = deployment().model_copy(
        update={
            "pricing": ModelPricingView(
                input_usd_per_million_tokens=Decimal(2),
                cached_input_usd_per_million_tokens=Decimal("0.5"),
                output_usd_per_million_tokens=Decimal(10),
                is_custom=True,
            )
        }
    )

    async def fake_aresponses(**_kwargs: Any) -> ResponsesAPIResponse:
        return response(cost=999)

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    result = await LiteLLMResponsesAdapter().create(custom, {"input": "hello"})

    assert result.accounting.cost_usd == Decimal("0.000037")


@pytest.mark.asyncio
async def test_adapter_custom_pricing_normalizes_anthropic_cache_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom = deployment().model_copy(
        update={
            "pricing": ModelPricingView(
                input_usd_per_million_tokens=Decimal(2),
                cached_input_usd_per_million_tokens=Decimal("0.5"),
                output_usd_per_million_tokens=Decimal(10),
                is_custom=True,
            )
        }
    )

    async def fake_aresponses(**_kwargs: Any) -> dict[str, Any]:
        return {
            "id": "resp_1",
            "model": "anthropic/private-model",
            "usage": {
                "prompt_tokens": 3,
                "completion_tokens": 3,
                "total_tokens": 8,
                "cache_read_input_tokens": 2,
            },
            "_hidden_params": {"response_cost": 999},
        }

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    result = await LiteLLMResponsesAdapter().create(custom, {"input": "hello"})

    assert result.accounting.cost_usd == Decimal("0.000037")


@pytest.mark.asyncio
async def test_adapter_omits_cost_without_complete_pricing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_aresponses(**_kwargs: Any) -> ResponsesAPIResponse:
        return response(cost=0.00125)

    monkeypatch.setattr("proxy.llm.adapter.litellm.aresponses", fake_aresponses)

    result = await LiteLLMResponsesAdapter().create(
        deployment().model_copy(update={"pricing": None}), {"input": "hello"}
    )

    assert result.accounting.cost_usd is None
