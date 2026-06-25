# agent-proxy

A FastAPI reverse proxy that secures and exposes upstream MCP (Model Context Protocol) HTTP servers behind authenticated endpoints. Clients authenticate to the proxy; the proxy strips auth headers and forwards requests upstream.

## Features

- Expose multiple upstream MCP servers at `/mcp/{name}`
- Group servers behind shared authentication providers (OIDC, Entra ID, or disabled/anonymous)
- Publish OAuth protected-resource metadata at `/.well-known/oauth-protected-resource/mcp/{name}`
- Bind MCP sessions to the authenticated principal that initialised them — one user cannot reuse another's session
- Filter proxy-only and hop-by-hop headers from forwarded requests and responses
- Support both buffered and streaming (SSE) upstream responses

## Quick Start

```bash
# Start Postgres, Keycloak, and the example MCP server
just compose

# Start the proxy
uv run proxy run
```

The proxy listens on `http://127.0.0.1:8008` by default. See [Configuration](#configuration) to customise.

---

## Usage

### Endpoints

| Method   | Path                                               | Description                                      |
|----------|----------------------------------------------------|--------------------------------------------------|
| `POST`   | `/mcp/{name}`                                      | Proxy a JSON-RPC request to the named MCP server |
| `GET`    | `/mcp/{name}`                                      | Proxy a GET request (e.g. SSE stream)            |
| `DELETE` | `/mcp/{name}`                                      | Proxy a DELETE request (e.g. session teardown)   |
| `GET`    | `/.well-known/oauth-protected-resource/mcp/{name}` | OAuth protected-resource metadata (RFC 8414)     |

### Smoke Test

```bash
TOKEN="<access-token>"

curl \
  -X POST http://localhost:8008/mcp/my-server \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke-test","version":"0.1.0"}}}'
```


## Configuration

Configuration is loaded from environment variables (prefix `PROXY__`, nested delimiter `__`) and from `.proxy/config.yaml`. Set `PROXY_CONFIG_FILE` to use a different YAML path.

### Minimal Example

```yaml
mcp:
  groups:
    - name: my-group
      auth:
        provider: oidc
        issuer: "http://localhost:8080/realms/agent-proxy"
      default_required_scopes:
        - mcp.access
      servers:
        - name: my-server
          resource: "http://localhost:8008/mcp/my-server"
          endpoint: "http://upstream:8931/mcp"
```

### Full Reference

```yaml
host:
  address: 127.0.0.1
  port: 8008

middleware:
  cors:
    origins:
      - "*"
    allow_credentials: false

database:
  address: 127.0.0.1
  port: 5432
  username: postgres
  password: postgres
  database: agent_proxy
  sslmode: disable
  options: {}

strip_headers:
  - connection
  - keep-alive
  - proxy-authenticate
  - proxy-authorization
  - te
  - trailer
  - transfer-encoding
  - upgrade

mcp:
  groups:
    - name: my-group
      auth:
        provider: oidc
        issuer: "http://localhost:8080/realms/agent-proxy"
      default_authorization_scopes:
        - openid
        - profile
        - mcp.access
      default_required_scopes:
        - mcp.access
      servers:
        - name: my-server
          description: "My upstream MCP server"
          resource: "http://localhost:8008/mcp/my-server"
          endpoint: "http://localhost:8931/mcp"
          accepted_audiences:
            - "api://<additional-audience>"
```

### Config Details

**Auth providers** are selected via the `provider` discriminator:

| Provider   | Type               | Notes                                                               |
|------------|--------------------|---------------------------------------------------------------------|
| `disabled` | No authentication  | Requests accepted as `anonymous` principal                          |
| `oidc`     | Generic OIDC       | Validates JWT against issuer's JWKS                                 |
| `entra_id` | Microsoft Entra ID | Convenience wrapper around OIDC; can derive issuer from `tenant_id` |

**Server-level scope inheritance:**

- `authorization_scopes` — advertised to OAuth clients in resource metadata. Falls back to `default_authorization_scopes`, then to `required_scopes`.
- `required_scopes` — enforced on incoming access tokens. Falls back to `default_required_scopes`.
- Server-level values always override group defaults.

**Protected groups** (non-`disabled`) require every server to set a `resource` URL. This is the OAuth protected-resource identifier that access-token audiences are matched against.

---

## Authentication & Authorisation

```
            ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  Client ──▶│  Proxy      │────▶│  Auth        │────▶│  Upstream   │
            │  /mcp/{name}│     │  Provider    │     │  MCP Server │
            └─────────────┘     └──────────────┘     └─────────────┘
                  │                                       │
                  │  /.well-known/oauth-protected-        │  mcp-session-id
                  │  resource/mcp/{name}                  │
                  ▼                                       ▼
            MCP Client                             MCP Session
            discovers                               bound to
            auth server                             principal
```

1. An MCP client requests the protected-resource metadata endpoint to learn the authorisation server URL and required scopes.
2. The client obtains an access token from the authorisation server.
3. The client sends the token as `Authorization: Bearer <token>` to the proxy.
4. The proxy validates the token (signature, issuer, audience, scopes) against the server's auth provider.
5. Missing or malformed tokens → `401` with `WWW-Authenticate`.
6. Tokens lacking required scopes → `403`.
7. Valid requests are forwarded upstream; the `Authorization` header is **not** sent upstream.

### Token Validation

For OIDC-backed groups, the proxy fetches:

- `/.well-known/openid-configuration` from the configured issuer
- JWKS from the URI advertised in discovery metadata

Validation steps:

- JWT signature verification using the matching JWK (by `kid`)
- Allowed signing algorithm (default: `RS256`)
- Issuer match
- `exp` and `iat` with configurable clock skew (default: 30s)
- Required claims: `sub`, `aud`, `iss`, `exp`, `iat`
- Audience matched against server `resource` + `accepted_audiences`
- Required scopes from `scp`, `scope`, or `roles` claims

### Entra ID Setup

```yaml
auth:
  provider: entra_id
  issuer: "https://login.microsoftonline.com/<tenant-id>/v2.0"
```

Or derive from tenant:

```yaml
auth:
  provider: entra_id
  tenant_id: "<tenant-id>"
```

**Proxy API registration:**

1. Create an app registration for the proxy (e.g. `agent-proxy-api`)
2. Set an Application ID URI (e.g. `api://<client-id>`)
3. Add a delegated scope (`mcp.access`) and/or an app role (`mcp.access`)
4. Configure the MCP server's `resource` as the URL clients connect to
5. Add the Application ID URI to `accepted_audiences`

**Client registration:**

- Public clients (desktop, VS Code, Copilot): authorisation-code flow with redirect URIs
- Confidential clients (services): client-credentials flow with secret or certificate
- Grant API permissions for the proxy API and admin consent if required

The proxy checks `scp` (delegated), `roles` (app roles), and `scope` claims, so the same scope requirement works for both user tokens and service principals.

---

## Session Handling

The proxy keeps a protected-session ownership registry in Postgres so one principal cannot reuse another's MCP session.

- On `initialize`, if the upstream responds with `MCP-Session-Id`, the proxy stores `(server, session_id, issuer, subject, client_id)`
- Subsequent requests with `MCP-Session-Id` must authenticate as the same `(issuer, subject)` pair
- If a different principal attempts reuse → `409 Conflict`
- On `DELETE` with `2xx` response → session binding is removed
- On upstream `404` → stale session binding is removed
- If the proxy loses its binding (e.g. restart) but the upstream still accepts the session, the session is re-bound on the next successful request

---

## Local Development

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/)
- Docker

### Setup

```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
just hook

# Start dependent services (Postgres, Keycloak, example MCP server)
just compose
```

### Run

```bash
# Start the proxy in dev mode (compose + run)
just dev

# Or separately:
uv run proxy run
```

### Local Keycloak Details

| Item                     | Value                                  |
|--------------------------|----------------------------------------|
| Realm                    | `agent-proxy`                          |
| Admin console            | `admin` / `admin`                      |
| Static local client      | `local-mcp-client`                     |
| VS Code / Copilot client | `aebc6443-996d-45c2-90f0-388ff96faa56` |
| Test user                | `admin` / `admin`                      |
| Keycloak version         | 26.4                                   |

The `mcp.access` client scope includes an audience mapper that emits the proxy's resource URL. Anonymous dynamic client registration is enabled for `localhost`, `127.0.0.1`, and `opencode.ai`.

### Client Integration

Clients that support OAuth-protected MCP servers discover the proxy's OAuth endpoints automatically using the protected-resource metadata at `/.well-known/oauth-protected-resource/mcp/{name}`. They then fetch RFC 8414 authorisation-server metadata from the advertised issuer.

- **Codex:** configure the MCP server URL as `http://localhost:8008/mcp/my-server`, then run `codex mcp login my-server`
- **OpenCode:** configure a remote MCP server with URL `http://localhost:8008/mcp/my-server`, then run `opencode mcp auth my-server`

### Troubleshooting

```
Policy 'Trusted Hosts' rejected request to client-registration service.
```

Recreate the Keycloak container and volume so the updated realm is imported:

```bash
docker compose down -v && just compose
```

---

## Testing

```bash
# Lint
just lint

# Type check
just typecheck

# Run all tests (unit + integration)
just test

# Integration tests only (requires Docker)
just test-integration

# Specific test groups
uv run pytest tests/integration/test_metadata.py -q
uv run pytest tests/integration/test_auth.py -q
uv run pytest tests/integration/test_mcp_proxy.py -q
```

---

## Commands

```bash
# Print current configuration as JSON
uv run proxy config

# Write JSON Schema for configuration
uv run proxy config-schema ./resources/config.schema.json

# Run the application (uvicorn)
uv run proxy run --host 127.0.0.1 --port 8008

# Generate config schema
just config-schema

# Start MCP Inspector
just inspector
```

---

## Project Scripts (`just`)

| Command                 | Description                               |
|-------------------------|-------------------------------------------|
| `just install`          | Install dependencies and pre-commit hooks |
| `just lint`             | Run linter                                |
| `just typecheck`        | Run type checker                          |
| `just test`             | Run all tests                             |
| `just test-integration` | Run Docker-backed integration tests       |
| `just compose`          | Start Docker services                     |
| `just stop`             | Stop Docker services                      |
| `just dev`              | Start services + proxy                    |
| `just config-schema`    | Generate configuration JSON Schema        |
| `just publish`          | Build and publish to PyPI                 |
| `just inspector`        | Launch MCP Inspector                      |
