from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import suppress
from typing import Any, cast

import litellm
from pydantic import BaseModel

from proxy.model_deployments.schemas import ResolvedModelDeployment


class LLMUpstreamError(RuntimeError):
    """Sanitized upstream failure with only gateway-safe classification."""

    def __init__(self, *, status_code: int | None, error_type: str) -> None:
        super().__init__("The upstream model request failed.")
        self.status_code = status_code
        self.error_type = error_type


class InvalidLLMResponse(RuntimeError):
    """Raised when LiteLLM returns an unsupported response representation."""


class LiteLLMResponsesAdapter:
    """Call LiteLLM directly without exposing its types to public layers."""

    async def create(
        self,
        deployment: ResolvedModelDeployment,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await litellm.aresponses(
                **self._arguments(deployment, request, stream=False)
            )
            return normalize_response(response, deployment.name)
        except Exception as error:
            raise _upstream_error(error) from error

    async def stream(
        self,
        deployment: ResolvedModelDeployment,
        request: Mapping[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        response: Any = None
        try:
            response = await litellm.aresponses(
                **self._arguments(deployment, request, stream=True)
            )
            async for event in cast(AsyncIterator[Any], response):
                yield normalize_response(event, deployment.name)
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
