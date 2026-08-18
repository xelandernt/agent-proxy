from __future__ import annotations

from typing import Any, Literal, cast

from openai.types.responses.response_create_params import (
    ResponseCreateParams,
    ResponseCreateParamsNonStreaming,
    ResponseCreateParamsStreaming,
)
from pydantic import BaseModel, RootModel, model_validator

_RESPONSE_CREATE_FIELDS = frozenset(
    ResponseCreateParamsNonStreaming.__required_keys__
    | ResponseCreateParamsNonStreaming.__optional_keys__
    | ResponseCreateParamsStreaming.__required_keys__
    | ResponseCreateParamsStreaming.__optional_keys__
)


class ResponsesRequest(RootModel[dict[str, Any]]):
    """OpenAI Responses request with the gateway's routing requirements."""

    @model_validator(mode="before")
    @classmethod
    def reject_unknown_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            unknown = sorted(set(value) - _RESPONSE_CREATE_FIELDS)
            if unknown:
                raise ValueError(f"Unknown request fields: {', '.join(unknown)}")
        return value

    @model_validator(mode="after")
    def validate_gateway_requirements(self) -> ResponsesRequest:
        model = self.root.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError("model is required.")
        stream = self.root.get("stream")
        if stream is not None and not isinstance(stream, bool):
            raise ValueError("stream must be a boolean.")
        return self

    @property
    def params(self) -> ResponseCreateParams:
        return cast(ResponseCreateParams, self.root)

    @property
    def model(self) -> str:
        return cast(str, self.root["model"])

    @property
    def stream(self) -> bool:
        return self.root.get("stream") is True

    def adapter_payload(self) -> dict[str, object]:
        payload = cast(
            dict[str, object],
            self.model_dump(mode="json", exclude_none=True),
        )
        payload.pop("model", None)
        payload.pop("stream", None)
        return payload


class OpenAIModel(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str = "agent-proxy"


class OpenAIModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[OpenAIModel]


class OpenAIErrorBody(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class OpenAIErrorEnvelope(BaseModel):
    error: OpenAIErrorBody
