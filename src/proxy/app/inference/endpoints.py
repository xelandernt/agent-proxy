from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from proxy.app.dependencies import InferenceServiceDep, ModelDeploymentServiceDep
from proxy.app.inference.auth import ProxyApiKeyDep
from proxy.app.inference.errors import OpenAIErrorException
from proxy.app.inference.schemas import (
    OpenAIErrorEnvelope,
    OpenAIModel,
    OpenAIModelList,
    ResponsesRequest,
)

router = APIRouter(prefix="/v1", tags=["openai"])


@router.get("/models", response_model=OpenAIModelList)
async def list_models(
    key: ProxyApiKeyDep,
    models: ModelDeploymentServiceDep,
) -> OpenAIModelList:
    available = {model.name: model for model in await models.list()}
    return OpenAIModelList(
        data=[
            OpenAIModel(
                id=name,
                created=int(available[name].created_at.timestamp()),
            )
            for name in sorted(key.models)
            if name in available
        ]
    )


@router.post("/responses")
async def create_response(
    payload: ResponsesRequest,
    key: ProxyApiKeyDep,
    service: InferenceServiceDep,
):
    if not payload.stream:
        return await service.create(key, payload)
    return StreamingResponse(
        _stream(service, key, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream(
    service: InferenceServiceDep,
    key: ProxyApiKeyDep,
    payload: ResponsesRequest,
) -> AsyncIterator[str]:
    try:
        async for event in service.stream(key, payload):
            event_type = event.get("type")
            if not isinstance(event_type, str):
                event_type = "message"
            data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            yield f"event: {event_type}\ndata: {data}\n\n"
    except OpenAIErrorException as error:
        envelope = OpenAIErrorEnvelope(error=error.body).model_dump(mode="json")
        data = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        yield f"event: error\ndata: {data}\n\n"
