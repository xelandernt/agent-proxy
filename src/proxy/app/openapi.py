from __future__ import annotations

from importlib.metadata import version
from typing import Annotated, Final, Literal

from fastapi import Header, Security
from fastapi.openapi.models import OpenAPI, PathItem
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from proxy.settings import GatewayConfig, McpServerConfig

MCP_PROTOCOL_VERSION: Final = "2026-07-28"
OPENAPI_VERSION: Final = "3.1.0"
BEARER_SCHEME_NAME: Final = "BearerAuth"
OPENAPI_DOCUMENT_ADAPTER: Final = TypeAdapter(dict[str, JsonValue])
DOCUMENTATION_ONLY_SCHEMAS: Final = frozenset(
    {"HTTPValidationError", "ValidationError"}
)

bearer_auth = HTTPBearer(
    scheme_name=BEARER_SCHEME_NAME,
    description=(
        "Bearer access token obtained through the endpoint's OAuth protected "
        "resource discovery flow."
    ),
)


class JsonRpcRequest(BaseModel):
    """Typed JSON-RPC request envelope accepted by modern MCP endpoints."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: str | int
    method: str = Field(description="MCP method named by the MCP-Method header.")
    params: dict[str, JsonValue] | None = None


class JsonRpcSuccess(BaseModel):
    """Successful JSON-RPC response envelope."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: str | int
    result: JsonValue


class JsonRpcErrorDetails(BaseModel):
    """JSON-RPC error returned by an MCP server."""

    model_config = ConfigDict(extra="forbid")

    code: int
    message: str
    data: JsonValue | None = None


class JsonRpcFailure(BaseModel):
    """Failed JSON-RPC response envelope."""

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: str | int | None
    error: JsonRpcErrorDetails


type JsonRpcResponse = JsonRpcSuccess | JsonRpcFailure
type OpenApiDocument = dict[str, JsonValue]


async def document_mcp_request(
    request: JsonRpcRequest,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_auth)],
    mcp_protocol_version: Annotated[
        Literal["2026-07-28"],
        Header(
            alias="MCP-Protocol-Version",
            description="Required modern MCP protocol version.",
        ),
    ],
    mcp_method: Annotated[
        str,
        Header(
            alias="MCP-Method",
            description="MCP method matching the JSON-RPC request method.",
        ),
    ],
) -> JsonRpcResponse:
    """Describe the MCP contract without registering a runtime endpoint."""

    del request, credentials, mcp_protocol_version, mcp_method
    raise RuntimeError("OpenAPI-only endpoint must never be called.")


def create_openapi_route(server: McpServerConfig) -> APIRoute:
    """Create one documentation-only route for a configured MCP server."""

    return APIRoute(
        path=f"/{server.name}/mcp",
        endpoint=document_mcp_request,
        methods={"POST"},
        operation_id=f"{server.name}_mcp",
        name=f"{server.name} MCP",
        summary=f"Call the {server.name} MCP server",
        description=(
            f"Authenticated MCP {MCP_PROTOCOL_VERSION} endpoint. Discover its "
            "authorization server through "
            f"`/.well-known/oauth-protected-resource/{server.name}/mcp`."
        ),
        response_model=JsonRpcResponse,
        responses={
            401: {"description": "A valid bearer access token is required."},
            403: {"description": "The access token lacks a required scope."},
        },
        tags=["MCP servers"],
    )


def create_openapi_document(config: GatewayConfig) -> OpenApiDocument:
    """Generate the public API document without private gateway configuration."""

    routes = [create_openapi_route(server) for server in config.servers]
    untrusted_document = get_openapi(
        title="agent-proxy",
        version=version("agent-proxy"),
        openapi_version=OPENAPI_VERSION,
        summary="Authenticated access to modern MCP servers.",
        description=(
            f"Authentication gateway for MCP {MCP_PROTOCOL_VERSION}. MCP tools, "
            "resources, and prompts are discovered through the protocol at runtime."
        ),
        routes=routes,
        tags=[
            {
                "name": "MCP servers",
                "description": "Configured authenticated MCP endpoints.",
            }
        ],
        servers=[{"url": str(config.public_base_url)}],
    )
    document = OpenAPI.model_validate(untrusted_document)
    if document.paths is None or document.components is None:
        raise ValueError("FastAPI generated an incomplete OpenAPI document.")

    for server in config.servers:
        path = f"/{server.name}/mcp"
        path_item = PathItem.model_validate(document.paths[path])
        if path_item.post is None or path_item.post.responses is None:
            raise ValueError(
                f"FastAPI omitted the documented POST operation for {path}."
            )
        path_item.post.responses.pop("422", None)
        document.paths[path] = path_item

    if document.components.schemas is not None:
        for schema_name in DOCUMENTATION_ONLY_SCHEMAS:
            document.components.schemas.pop(schema_name, None)

    return OPENAPI_DOCUMENT_ADAPTER.validate_python(
        document.model_dump(mode="json", by_alias=True, exclude_none=True)
    )
