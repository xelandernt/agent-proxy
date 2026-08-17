from __future__ import annotations

from typing import cast, get_args

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, TypeAdapter

from proxy.providers import ManagedAuthProviderConfig
from proxy.servers.constants import NAME_PATTERN

AUTH_PROVIDER_ADAPTER = TypeAdapter(ManagedAuthProviderConfig)


class AuthProviderDefinition(BaseModel):
    """A named reusable MCP authentication definition."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    auth: ManagedAuthProviderConfig


def config_to_auth_payload(config: ManagedAuthProviderConfig) -> dict:
    """Serialize a typed provider definition to JSON-safe persistence data."""

    return cast(
        dict,
        _jsonable(AUTH_PROVIDER_ADAPTER.dump_python(config, mode="python")),
    )


def config_to_public_auth_payload(
    config: ManagedAuthProviderConfig,
) -> dict[str, object]:
    """Serialize provider settings without returning any credential values."""

    payload = _public_jsonable(config)
    return cast(dict[str, object], payload)


def _public_jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        raw = value.model_dump(mode="python")
        fields = type(value).model_fields
        return {
            key: converted
            for key, item in raw.items()
            if not (
                key in fields and _annotation_contains_secret(fields[key].annotation)
            )
            and (converted := _public_jsonable(item)) is not _OmitSecret
        }
    if isinstance(value, SecretStr):
        return _OmitSecret
    if isinstance(value, dict):
        return {
            key: converted
            for key, item in value.items()
            if (converted := _public_jsonable(item)) is not _OmitSecret
        }
    if isinstance(value, list):
        return [
            converted
            for item in value
            if (converted := _public_jsonable(item)) is not _OmitSecret
        ]
    if isinstance(value, AnyHttpUrl):
        return str(value)
    return value


def _annotation_contains_secret(annotation: object) -> bool:
    return annotation is SecretStr or any(
        _annotation_contains_secret(argument) for argument in get_args(annotation)
    )


class _OmitSecretType:
    pass


_OmitSecret = _OmitSecretType()


def _jsonable(value: object) -> object:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, AnyHttpUrl):
        return str(value)
    return value
