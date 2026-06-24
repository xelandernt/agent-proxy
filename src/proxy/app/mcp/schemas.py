from pydantic import BaseModel, Field


class OAuthProtectedResourceMetadata(BaseModel):
    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str] = Field(default_factory=list)
    bearer_methods_supported: list[str] = Field(default_factory=lambda: ["header"])
    resource_name: str
