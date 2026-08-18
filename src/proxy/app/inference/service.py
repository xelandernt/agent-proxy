from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from proxy.api_keys.schemas import AuthenticatedApiKey
from proxy.app.inference.errors import OpenAIErrorException
from proxy.app.inference.schemas import ResponsesRequest
from proxy.app.model_usage.recorder import ModelUsageRecord, ModelUsageRecorder
from proxy.llm.adapter import LiteLLMResponsesAdapter, LLMUpstreamError
from proxy.model_deployments.repository import ModelDeploymentNotFound
from proxy.model_deployments.schemas import ResolvedModelDeployment
from proxy.model_deployments.service import ModelDeploymentService
from proxy.security.credentials import (
    CredentialEncryptionUnavailable,
    InvalidCredentialCiphertext,
)


class InferenceService:
    def __init__(
        self,
        models: ModelDeploymentService,
        adapter: LiteLLMResponsesAdapter,
        usage: ModelUsageRecorder,
    ) -> None:
        self._models = models
        self._adapter = adapter
        self._usage = usage

    async def create(
        self,
        key: AuthenticatedApiKey,
        request: ResponsesRequest,
    ) -> dict[str, Any]:
        started = time.monotonic()
        deployment = await self._authorized_deployment(
            key, request.model, started, False
        )
        try:
            response = await self._adapter.create(deployment, request.adapter_payload())
        except LLMUpstreamError as error:
            mapped = _map_upstream_error(error)
            self._record(
                key,
                deployment,
                request.model,
                started,
                False,
                mapped.status_code,
                error.error_type,
            )
            raise mapped from error
        self._record(
            key,
            deployment,
            request.model,
            started,
            False,
            200,
            None,
            response,
        )
        return response

    async def stream(
        self,
        key: AuthenticatedApiKey,
        request: ResponsesRequest,
    ) -> AsyncIterator[dict[str, Any]]:
        started = time.monotonic()
        deployment = await self._authorized_deployment(
            key, request.model, started, True
        )
        terminal: dict[str, Any] | None = None
        try:
            async for event in self._adapter.stream(
                deployment, request.adapter_payload()
            ):
                if event.get("type") == "response.completed":
                    response = event.get("response")
                    if isinstance(response, dict):
                        terminal = response
                yield event
        except LLMUpstreamError as error:
            mapped = _map_upstream_error(error)
            self._record(
                key,
                deployment,
                request.model,
                started,
                True,
                mapped.status_code,
                error.error_type,
            )
            raise mapped from error
        except BaseException:
            self._record(
                key,
                deployment,
                request.model,
                started,
                True,
                499,
                "client_disconnected",
            )
            raise
        else:
            self._record(
                key,
                deployment,
                request.model,
                started,
                True,
                200,
                None,
                terminal,
            )

    async def _authorized_deployment(
        self,
        key: AuthenticatedApiKey,
        model_name: str,
        started: float,
        streaming: bool,
    ) -> ResolvedModelDeployment:
        if model_name not in key.models:
            self._record(
                key, None, model_name, started, streaming, 404, "model_not_found"
            )
            raise _model_not_found(model_name)
        try:
            return await self._models.resolve(model_name)
        except ModelDeploymentNotFound as error:
            self._record(
                key, None, model_name, started, streaming, 404, "model_not_found"
            )
            raise _model_not_found(model_name) from error
        except CredentialEncryptionUnavailable as error:
            self._record(
                key, None, model_name, started, streaming, 503, "gateway_unavailable"
            )
            raise OpenAIErrorException(
                503,
                "Model inference is not configured.",
                error_type="server_error",
                code="gateway_unavailable",
            ) from error
        except InvalidCredentialCiphertext as error:
            self._record(
                key, None, model_name, started, streaming, 500, "credential_error"
            )
            raise OpenAIErrorException(
                500,
                "The model deployment is unavailable.",
                error_type="server_error",
                code="model_unavailable",
            ) from error

    def _record(
        self,
        key: AuthenticatedApiKey,
        deployment: ResolvedModelDeployment | None,
        model_name: str,
        started: float,
        streaming: bool,
        status_code: int,
        error_type: str | None,
        response: dict[str, Any] | None = None,
    ) -> None:
        input_tokens, output_tokens, total_tokens = _usage(response)
        self._usage.record(
            ModelUsageRecord(
                user_id=key.user_id,
                api_key_id=key.id,
                model_name=model_name,
                provider=_provider(deployment.upstream_model) if deployment else None,
                status_code=status_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                duration_ms=max(0, round((time.monotonic() - started) * 1000)),
                error_type=error_type,
                streaming=streaming,
                ts=datetime.now(UTC),
            )
        )


def _model_not_found(model_name: str) -> OpenAIErrorException:
    return OpenAIErrorException(
        404,
        f"The model '{model_name}' does not exist or is not available to this API key.",
        error_type="invalid_request_error",
        param="model",
        code="model_not_found",
    )


def _map_upstream_error(error: LLMUpstreamError) -> OpenAIErrorException:
    if error.status_code == 429:
        return OpenAIErrorException(
            429,
            "The upstream model is rate limited.",
            error_type="rate_limit_error",
            code="upstream_rate_limit",
        )
    if error.status_code in {408, 504} or "timeout" in error.error_type.lower():
        return OpenAIErrorException(
            504,
            "The upstream model timed out.",
            error_type="server_error",
            code="upstream_timeout",
        )
    return OpenAIErrorException(
        502,
        "The upstream model request failed.",
        error_type="server_error",
        code="upstream_error",
    )


def _usage(
    response: dict[str, Any] | None,
) -> tuple[int | None, int | None, int | None]:
    usage = response.get("usage") if response else None
    if not isinstance(usage, dict):
        return None, None, None
    return (
        _integer(usage.get("input_tokens", usage.get("prompt_tokens"))),
        _integer(usage.get("output_tokens", usage.get("completion_tokens"))),
        _integer(usage.get("total_tokens")),
    )


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _provider(upstream_model: str) -> str:
    provider, separator, _ = upstream_model.partition("/")
    return provider if separator else "openai"
