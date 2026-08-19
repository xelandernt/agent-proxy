from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr

from proxy.servers.constants import NAME_PATTERN


class _ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenAIProviderConfig(_ProviderConfig):
    provider: Literal["openai"]
    api_key: SecretStr | None = None
    organization: str | None = Field(default=None, min_length=1, max_length=255)
    project: str | None = Field(default=None, min_length=1, max_length=255)


class AnthropicProviderConfig(_ProviderConfig):
    provider: Literal["anthropic"]
    api_key: SecretStr | None = None


class AzureOpenAIProviderConfig(_ProviderConfig):
    provider: Literal["azure_openai"]
    api_key: SecretStr | None = None
    endpoint: AnyHttpUrl = Field(max_length=2048)
    api_version: str = Field(min_length=1, max_length=100)


class OpenAICompatibleProviderConfig(_ProviderConfig):
    provider: Literal["openai_compatible"]
    api_key: SecretStr | None = None
    base_url: AnyHttpUrl = Field(max_length=2048)


class BedrockDefaultCredentials(_ProviderConfig):
    type: Literal["default"]


class BedrockApiKeyCredentials(_ProviderConfig):
    type: Literal["api_key"]
    api_key: SecretStr | None = None


class BedrockAccessKeyCredentials(_ProviderConfig):
    type: Literal["access_keys"]
    access_key_id: SecretStr | None = None
    secret_access_key: SecretStr | None = None
    session_token: SecretStr | None = None


BedrockCredentials = Annotated[
    BedrockDefaultCredentials | BedrockApiKeyCredentials | BedrockAccessKeyCredentials,
    Field(discriminator="type"),
]


class BedrockProviderConfig(_ProviderConfig):
    provider: Literal["bedrock"]
    region: str = Field(min_length=1, max_length=100)
    credentials: BedrockCredentials


ModelProviderConfig = Annotated[
    OpenAIProviderConfig
    | AnthropicProviderConfig
    | AzureOpenAIProviderConfig
    | BedrockProviderConfig
    | OpenAICompatibleProviderConfig,
    Field(discriminator="provider"),
]


class ModelProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    config: ModelProviderConfig


class ModelProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: ModelProviderConfig


class ModelProviderView(BaseModel):
    name: str
    config: ModelProviderConfig
    credential_names: list[str]
    created_at: datetime
    updated_at: datetime
