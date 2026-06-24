from pydantic import BaseModel, Field


class OAuthProtectedResourceMetadata(BaseModel):
    """OAuth protected resource metadata (RFC 8414).

    Describes the protected resource for OAuth client discovery.

    Attributes:
        resource: The canonical resource URI of the MCP server.
        authorization_servers: URLs of the authorisation servers.
        scopes_supported: Scopes supported by the authorisation server.
        bearer_methods_supported: Bearer token delivery methods.
        resource_name: Human-readable name of the MCP server.
    """

    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str] = Field(default_factory=list)
    bearer_methods_supported: list[str] = Field(default_factory=lambda: ["header"])
    resource_name: str
