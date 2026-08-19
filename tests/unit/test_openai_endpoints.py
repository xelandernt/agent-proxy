from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi.testclient import TestClient
from openai import AsyncOpenAI

from proxy.api_keys.schemas import AuthenticatedApiKey
from proxy.app.dependencies import (
    get_api_key_service,
    get_inference_service,
    get_model_deployment_service,
)
from proxy.app.inference.schemas import ResponsesRequest
from proxy.app.main import create_app
from proxy.model_deployments.schemas import ModelDeploymentView
from proxy.settings import GatewayConfig

KEY_ID = UUID("4fb9ca09-2e2b-4e3f-ac94-630f911c8acf")
USER_ID = UUID("c8464904-f61b-48e3-9e87-ef0a1e15a05e")


class FakeKeyService:
    async def authenticate(self, plaintext: str) -> AuthenticatedApiKey | None:
        if plaintext != "ap_12345678_secret":
            return None
        return AuthenticatedApiKey(
            id=KEY_ID,
            user_id=USER_ID,
            models=frozenset({"alpha"}),
        )

    async def mark_used(self, _key_id: UUID) -> None:
        return None


class FakeModelService:
    async def list(self) -> list[ModelDeploymentView]:
        now = datetime(2026, 8, 18, tzinfo=UTC)
        return [
            ModelDeploymentView(
                name="alpha",
                provider="anthropic-production",
                model_id="claude-sonnet",
                pricing=None,
                created_at=now,
                updated_at=now,
            ),
            ModelDeploymentView(
                name="beta",
                provider="openai-production",
                model_id="gpt-5",
                pricing=None,
                created_at=now,
                updated_at=now,
            ),
        ]


class FakeInferenceService:
    async def create(
        self, _key: AuthenticatedApiKey, request: ResponsesRequest
    ) -> dict[str, object]:
        return {
            "id": "resp_1",
            "object": "response",
            "model": request.model,
            "output": [],
        }

    async def stream(
        self, _key: AuthenticatedApiKey, _request: ResponsesRequest
    ) -> AsyncIterator[dict[str, object]]:
        yield {"type": "response.created", "response": {"id": "resp_1"}}
        yield {"type": "response.output_text.delta", "delta": "hello"}
        yield {"type": "response.completed", "response": {"id": "resp_1"}}


def client() -> TestClient:
    app = app_with_fakes()
    return TestClient(app)


def app_with_fakes():
    config = GatewayConfig.model_validate(
        {
            "admin": {"auth": {"provider": "static"}},
            "user": {
                "auth": {
                    "provider": "jwt",
                    "public_key": "test-user-auth-secret",
                    "algorithm": "HS256",
                }
            },
            "model_gateway": {
                "credential_encryption_key": (
                    "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="
                )
            },
        }
    )
    app = create_app(config)
    app.dependency_overrides[get_api_key_service] = FakeKeyService
    app.dependency_overrides[get_model_deployment_service] = FakeModelService
    app.dependency_overrides[get_inference_service] = FakeInferenceService
    return app


def auth() -> dict[str, str]:
    return {"Authorization": "Bearer ap_12345678_secret"}


def test_models_requires_proxy_key_and_filters_scope() -> None:
    with client() as gateway:
        missing = gateway.get("/v1/models")
        valid = gateway.get("/v1/models", headers=auth())

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "invalid_api_key"
    assert valid.status_code == 200
    assert [model["id"] for model in valid.json()["data"]] == ["alpha"]
    assert valid.json()["data"][0]["owned_by"] == "agent-proxy"


def test_responses_accepts_openai_fields_and_rejects_unknown_fields() -> None:
    with client() as gateway:
        unknown = gateway.post(
            "/v1/responses",
            headers=auth(),
            json={"model": "alpha", "input": "hello", "not_an_openai_field": True},
        )
        stored = gateway.post(
            "/v1/responses",
            headers=auth(),
            json={
                "model": "alpha",
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "hello"}],
                    }
                ],
                "store": True,
            },
        )
        hosted_tool = gateway.post(
            "/v1/responses",
            headers=auth(),
            json={
                "model": "alpha",
                "input": "hello",
                "tools": [{"type": "web_search"}],
            },
        )

    assert unknown.status_code == 400
    assert unknown.json()["error"]["type"] == "invalid_request_error"
    assert stored.status_code == 200
    assert hosted_tool.status_code == 200


def test_v1_http_and_unhandled_failures_use_openai_error_envelopes() -> None:
    app = app_with_fakes()

    class FailingModelService:
        async def list(self) -> list[ModelDeploymentView]:
            raise RuntimeError("database password and internal details")

    app.dependency_overrides[get_model_deployment_service] = FailingModelService
    with TestClient(app, raise_server_exceptions=False) as gateway:
        missing = gateway.get("/v1/not-a-resource")
        failed = gateway.get("/v1/models", headers=auth())

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "internal_error"
    assert "password" not in failed.text


def test_responses_supports_text_reasoning_and_function_tools() -> None:
    with client() as gateway:
        response = gateway.post(
            "/v1/responses",
            headers=auth(),
            json={
                "model": "alpha",
                "input": "What is the weather?",
                "reasoning": {"effort": "medium"},
                "tools": [
                    {
                        "type": "function",
                        "name": "weather",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
                "tool_choice": {"type": "function", "name": "weather"},
            },
        )

    assert response.status_code == 200
    assert response.json()["model"] == "alpha"


def test_responses_streams_typed_sse_events() -> None:
    with client() as gateway:
        response = gateway.post(
            "/v1/responses",
            headers=auth(),
            json={"model": "alpha", "input": "hello", "stream": True},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: response.created\n" in response.text
    assert "event: response.output_text.delta\n" in response.text
    assert "event: response.completed\n" in response.text


async def test_official_openai_sdk_lists_models_and_consumes_responses() -> None:
    transport = httpx.ASGITransport(app=app_with_fakes())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://gateway.test",
    ) as http_client:
        sdk = AsyncOpenAI(
            api_key="ap_12345678_secret",
            base_url="http://gateway.test/v1",
            http_client=http_client,
        )
        models = await sdk.models.list()
        response = await sdk.responses.create(model="alpha", input="hello")
        stream = await sdk.responses.create(
            model="alpha",
            input="hello",
            stream=True,
        )
        event_types = [event.type async for event in stream]

    assert [model.id for model in models.data] == ["alpha"]
    assert response.model == "alpha"
    assert event_types == [
        "response.created",
        "response.output_text.delta",
        "response.completed",
    ]


async def test_official_openai_sdk_runs_client_managed_function_tool_loop() -> None:
    requests: list[ResponsesRequest] = []

    class ToolLoopService(FakeInferenceService):
        async def create(
            self,
            _key: AuthenticatedApiKey,
            request: ResponsesRequest,
        ) -> dict[str, object]:
            requests.append(request)
            if len(requests) == 1:
                output: list[dict[str, object]] = [
                    {
                        "id": "fc_1",
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "weather",
                        "arguments": "{}",
                        "status": "completed",
                    }
                ]
            else:
                output = [
                    {
                        "id": "msg_1",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Sunny",
                                "annotations": [],
                                "logprobs": [],
                            }
                        ],
                    }
                ]
            return {
                "id": f"resp_{len(requests)}",
                "object": "response",
                "model": request.model,
                "output": output,
            }

    app = app_with_fakes()
    app.dependency_overrides[get_inference_service] = ToolLoopService
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://gateway.test",
    ) as http_client:
        sdk = AsyncOpenAI(
            api_key="ap_12345678_secret",
            base_url="http://gateway.test/v1",
            http_client=http_client,
        )
        first = await sdk.responses.create(
            model="alpha",
            input="What is the weather?",
            tools=[
                {
                    "type": "function",
                    "name": "weather",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
        )
        call = first.output[0]
        second = await sdk.responses.create(
            model="alpha",
            input=[
                {"role": "user", "content": "What is the weather?"},
                {
                    "type": "function_call",
                    "id": call.id,
                    "call_id": call.call_id,  # type: ignore[union-attr]
                    "name": call.name,  # type: ignore[union-attr]
                    "arguments": call.arguments,  # type: ignore[union-attr]
                    "status": call.status,
                },
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,  # type: ignore[union-attr]
                    "output": "Sunny",
                },
            ],
        )

    assert second.output_text == "Sunny"
    assert len(requests) == 2
    input_items = requests[1].params.get("input")
    assert isinstance(input_items, list)
    assert input_items[-1]["type"] == "function_call_output"
