from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, SecretStr

from proxy.model_providers.repository import (
    ModelProviderNotFound,
    ModelProviderRepository,
)
from proxy.model_providers.schemas import (
    ModelProviderConfig,
    ModelProviderCreate,
    ModelProviderUpdate,
    ModelProviderView,
)
from proxy.security.credentials import CredentialCipher


class ModelProviderCredentialsMissing(ValueError):
    pass


class ModelProviderService:
    def __init__(
        self, repository: ModelProviderRepository, cipher: CredentialCipher
    ) -> None:
        self._repository = repository
        self._cipher = cipher

    async def list(self) -> list[ModelProviderView]:
        return [self._view(row) for row in await self._repository.list_all()]

    async def get(self, name: str) -> ModelProviderView:
        return self._view(await self._require(name))

    async def create(self, payload: ModelProviderCreate) -> ModelProviderView:
        config, credentials = _split_config(payload.config)
        _validate_credentials(config, credentials)
        row = await self._repository.create(
            name=payload.name,
            config=config,
            encrypted_credentials=self._cipher.encrypt(credentials),
            credential_names=sorted(credentials),
        )
        return self._view(row)

    async def update(
        self, name: str, payload: ModelProviderUpdate
    ) -> ModelProviderView:
        current = await self._require(name)
        config, supplied = _split_config(payload.config)
        current_mode = _credential_mode(current.config)
        next_mode = _credential_mode(config)
        credentials = (
            self._cipher.decrypt(current.encrypted_credentials)
            if current_mode == next_mode
            else {}
        )
        credentials.update(supplied)
        _validate_credentials(config, credentials)
        row = await self._repository.update(
            name,
            config=config,
            encrypted_credentials=self._cipher.encrypt(credentials),
            credential_names=sorted(credentials),
        )
        return self._view(row)

    async def delete(self, name: str) -> None:
        await self._repository.delete(name)

    async def resolve(
        self, name: str, model_id: str
    ) -> tuple[str, str | None, dict[str, Any], dict[str, str]]:
        row = await self._require(name)
        credentials = self._cipher.decrypt(row.encrypted_credentials)
        provider = row.config["provider"]
        upstream_model = _upstream_model(provider, model_id)
        settings: dict[str, Any] = {}
        api_base = None
        secrets: dict[str, str] = {}
        if provider == "openai":
            settings.update(
                {
                    key: row.config[key]
                    for key in ("organization", "project")
                    if row.config.get(key)
                }
            )
            secrets["api_key"] = credentials["api_key"]
        elif provider == "anthropic":
            secrets["api_key"] = credentials["api_key"]
        elif provider == "azure_openai":
            api_base = str(row.config["endpoint"])
            settings["api_version"] = row.config["api_version"]
            secrets["api_key"] = credentials["api_key"]
        elif provider == "openai_compatible":
            api_base = str(row.config["base_url"])
            secrets["api_key"] = credentials["api_key"]
        else:
            settings["aws_region_name"] = row.config["region"]
            auth_type = _credential_mode(row.config)[1]
            if auth_type == "api_key":
                secrets["api_key"] = credentials["api_key"]
            elif auth_type == "access_keys":
                secrets["aws_access_key_id"] = credentials["access_key_id"]
                secrets["aws_secret_access_key"] = credentials["secret_access_key"]
                if credentials.get("session_token"):
                    secrets["aws_session_token"] = credentials["session_token"]
        return upstream_model, api_base, settings, secrets

    async def upstream_model(self, name: str, model_id: str) -> str:
        row = await self._require(name)
        return _upstream_model(row.config["provider"], model_id)

    async def upstream_models(
        self, deployments: Sequence[tuple[str, str]]
    ) -> Sequence[str]:
        providers = {row.name: row for row in await self._repository.list_all()}
        return [
            _upstream_model(providers[name].config["provider"], model_id)
            for name, model_id in deployments
        ]

    async def _require(self, name: str):
        row = await self._repository.get(name)
        if row is None:
            raise ModelProviderNotFound(f"Unknown model provider '{name}'.")
        return row

    @staticmethod
    def _view(row) -> ModelProviderView:
        return ModelProviderView(
            name=row.name,
            config=row.config,
            credential_names=row.credential_names,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _upstream_model(provider: object, model_id: str) -> str:
    prefix = {
        "openai": "openai",
        "anthropic": "anthropic",
        "azure_openai": "azure",
        "bedrock": "bedrock",
        "openai_compatible": "openai",
    }[str(provider)]
    return f"{prefix}/{model_id}"


def _split_config(config: ModelProviderConfig) -> tuple[dict[str, Any], dict[str, str]]:
    raw = config.model_dump(mode="python")
    credentials: dict[str, str] = {}

    def strip(value: Any) -> Any:
        if isinstance(value, SecretStr):
            return None
        if isinstance(value, BaseModel):
            return strip(value.model_dump(mode="python"))
        if isinstance(value, dict):
            return {
                key: converted
                for key, item in value.items()
                if (converted := strip(item)) is not None
            }
        if isinstance(value, list):
            return [strip(item) for item in value]
        return str(value) if value.__class__.__name__ == "AnyHttpUrl" else value

    def collect(value: Any) -> None:
        if isinstance(value, BaseModel):
            for key, item in value.__dict__.items():
                if isinstance(item, SecretStr):
                    credentials[key] = item.get_secret_value()
                else:
                    collect(item)

    collect(config)
    return strip(raw), credentials


def _credential_mode(config: dict[str, Any]) -> tuple[str, str | None]:
    provider = str(config["provider"])
    if provider != "bedrock":
        return provider, None
    credentials = config.get("credentials", {})
    return provider, str(credentials.get("type"))


def _validate_credentials(config: dict[str, Any], credentials: dict[str, str]) -> None:
    provider, mode = _credential_mode(config)
    required = {"api_key"}
    if provider == "bedrock":
        required = (
            set()
            if mode == "default"
            else (
                {"api_key"}
                if mode == "api_key"
                else {"access_key_id", "secret_access_key"}
            )
        )
    missing = sorted(name for name in required if not credentials.get(name))
    if missing:
        raise ModelProviderCredentialsMissing(
            "Missing provider credentials: " + ", ".join(missing) + "."
        )
