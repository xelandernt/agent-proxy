from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import litellm
from pydantic import BaseModel

from proxy.model_deployments.schemas import ResolvedModelDeployment

COST_QUANTUM = Decimal("0.000000000001")


class LLMUpstreamError(RuntimeError):
    """Sanitized upstream failure with only gateway-safe classification."""

    def __init__(self, *, status_code: int | None, error_type: str) -> None:
        super().__init__("The upstream model request failed.")
        self.status_code = status_code
        self.error_type = error_type


class InvalidLLMResponse(RuntimeError):
    """Raised when LiteLLM returns an unsupported response representation."""


@dataclass(frozen=True, slots=True)
class LLMAccounting:
    """Validated accounting facts extracted from an untrusted LiteLLM result."""

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cost_usd: Decimal | None
    cached_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResult:
    """A public-safe payload paired with private accounting metadata."""

    payload: dict[str, Any]
    accounting: LLMAccounting


class LiteLLMResponsesAdapter:
    """Call LiteLLM directly without exposing its types to public layers."""

    async def create(
        self,
        deployment: ResolvedModelDeployment,
        request: Mapping[str, Any],
    ) -> LLMResult:
        try:
            response = await litellm.aresponses(
                **self._arguments(deployment, request, stream=False)
            )
            return _result(response, deployment)
        except Exception as error:
            raise _upstream_error(error) from error

    async def stream(
        self,
        deployment: ResolvedModelDeployment,
        request: Mapping[str, Any],
    ) -> AsyncIterator[LLMResult]:
        response: Any = None
        try:
            response = await litellm.aresponses(
                **self._arguments(deployment, request, stream=True)
            )
            async for event in cast(AsyncIterator[Any], response):
                yield _result(event, deployment, streaming=True)
        except Exception as error:
            raise _upstream_error(error) from error
        finally:
            close = cast(
                Callable[[], Awaitable[None]] | None,
                getattr(response, "aclose", None),
            )
            if close is not None:
                with suppress(Exception):
                    await close()

    @staticmethod
    def _arguments(
        deployment: ResolvedModelDeployment,
        request: Mapping[str, Any],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = dict(deployment.settings)
        arguments.update(deployment.secrets)
        arguments.update(request)
        arguments["model"] = deployment.upstream_model
        arguments["stream"] = stream
        if deployment.api_base is not None:
            arguments["api_base"] = deployment.api_base
        return arguments


def normalize_response(value: Any, public_model: str) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude_none=True)
    elif isinstance(value, Mapping):
        payload = dict(value)
    else:
        model_dump = getattr(value, "model_dump", None)
        if not callable(model_dump):
            raise InvalidLLMResponse("LiteLLM returned an unsupported response.")
        payload = model_dump(mode="json", exclude_none=True)
    if not isinstance(payload, dict):
        raise InvalidLLMResponse("LiteLLM returned a non-object response.")
    return _sanitize(payload, public_model)


def _result(
    value: Any,
    deployment: ResolvedModelDeployment,
    *,
    streaming: bool = False,
) -> LLMResult:
    payload = normalize_response(value, deployment.name)
    response = _terminal_response(value) if streaming else value
    return LLMResult(
        payload=payload,
        accounting=_accounting(
            response,
            deployment=deployment,
            calculate_cost=response is not None,
        ),
    )


def _terminal_response(value: Any) -> Any | None:
    event_type = _field(value, "type")
    if event_type not in {
        "response.completed",
        "response.failed",
        "response.incomplete",
    }:
        return None
    return _field(value, "response")


def _accounting(
    value: Any,
    *,
    deployment: ResolvedModelDeployment,
    calculate_cost: bool,
) -> LLMAccounting:
    usage = _field(value, "usage")
    input_details = _field(
        usage,
        "input_tokens_details",
        _field(usage, "prompt_tokens_details"),
    )
    cached_tokens = _field(input_details, "cached_tokens")
    if cached_tokens is None:
        cached_tokens = _field(
            usage,
            "cache_read_input_tokens",
            _field(usage, "prompt_cache_hit_tokens"),
        )
    cost = _response_cost(value, usage, deployment, calculate_cost=calculate_cost)
    return LLMAccounting(
        input_tokens=_non_negative_integer(
            _field(usage, "input_tokens", _field(usage, "prompt_tokens"))
        ),
        output_tokens=_non_negative_integer(
            _field(usage, "output_tokens", _field(usage, "completion_tokens"))
        ),
        total_tokens=_non_negative_integer(_field(usage, "total_tokens")),
        cached_tokens=_non_negative_integer(cached_tokens),
        cost_usd=cost,
    )


def _response_cost(
    value: Any,
    usage: Any,
    deployment: ResolvedModelDeployment,
    *,
    calculate_cost: bool,
) -> Decimal | None:
    pricing = deployment.pricing
    if pricing is None or not calculate_cost or value is None:
        return None
    if pricing.is_custom:
        custom_costs = {
            "input_cost_per_token": float(
                pricing.input_usd_per_million_tokens / 1_000_000
            ),
            "cache_read_input_token_cost": float(
                pricing.cached_input_usd_per_million_tokens / 1_000_000
            ),
            "output_cost_per_token": float(
                pricing.output_usd_per_million_tokens / 1_000_000
            ),
        }
        try:
            cost = _cost(
                litellm.completion_cost(
                    completion_response=value,
                    model=deployment.upstream_model,
                    custom_cost_per_token=custom_costs,
                )
            )
            return cost.quantize(COST_QUANTUM) if cost is not None else None
        except Exception:  # noqa: BLE001 - LiteLLM usage data is untrusted input.
            return None

    cost = _cost(_field(usage, "cost"))
    if cost is None:
        hidden = _field(value, "_hidden_params")
        if isinstance(hidden, Mapping):
            cost = _cost(hidden.get("response_cost"))
    if cost is not None:
        return cost
    try:
        return _cost(litellm.completion_cost(completion_response=value))
    except Exception:  # noqa: BLE001 - LiteLLM cost failures are untrusted input.
        return None


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _non_negative_integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _cost(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        cost = Decimal(str(value))
    except InvalidOperation:
        return None
    return cost if cost.is_finite() and cost >= 0 else None


def _sanitize(value: Any, public_model: str) -> Any:
    if isinstance(value, dict):
        return {
            key: public_model if key == "model" else _sanitize(item, public_model)
            for key, item in value.items()
            if not key.startswith("_hidden")
        }
    if isinstance(value, list):
        return [_sanitize(item, public_model) for item in value]
    return value


def _upstream_error(error: Exception) -> LLMUpstreamError:
    status_code = getattr(error, "status_code", None)
    return LLMUpstreamError(
        status_code=status_code if isinstance(status_code, int) else None,
        error_type=type(error).__name__,
    )
