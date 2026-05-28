# agent-proxy

FastAPI proxy for named MCP HTTP servers.

## Features

- exposes upstream MCP servers behind `/mcp/{name}`
- groups MCP servers behind shared auth providers
- supports anonymous passthrough, generic OIDC, and legacy Entra ID issuer config
- publishes MCP OAuth protected-resource metadata for protected servers
- binds protected MCP sessions to the authenticated principal that initialized them

## Configuration

Configuration is loaded from environment variables prefixed with `PROXY__` and from `.proxy/config.yaml`. Set `PROXY_CONFIG_FILE` to use a different YAML file.

```yaml
host:
  address: 127.0.0.1
  port: 8008

middleware:
  cors:
    origins:
      - "*"
    allow_credentials: false

session_registry:
  address: 127.0.0.1
  port: 5432
  username: postgres
  password: postgres
  database: agent_proxy
  sslmode: disable

mcp:
  groups:
    - name: playwright
      auth:
        provider: oidc
        issuer: "http://localhost:8080/realms/agent-proxy"
      default_required_scopes:
        - "mcp.access"
      servers:
        - name: playwright
          resource: "http://localhost:8008/mcp/playwright"
          endpoint: "http://localhost:8931/mcp"
```

Each group shares one auth provider. Servers in protected groups must configure `resource`; access-token audiences are matched against that URL. `required_scopes` can be set per server and otherwise inherits `default_required_scopes` from the group.

`session_registry.url` is derived from those top-level database fields, so application code can use one DSN while config stays split into explicit parts.

## Authentication Flow

MCP clients authenticate to the proxy, not to the upstream MCP server. The proxy validates the client credential, enforces server access rules, strips proxy-only authentication headers, and then forwards the MCP request upstream.

1. A client calls `POST /mcp/{name}`, `GET /mcp/{name}`, or `DELETE /mcp/{name}`.
2. FastAPI resolves `{name}` to a configured MCP server and group.
3. For `disabled` groups, the request is accepted as an anonymous principal.
4. For `oidc` and `entra_id` groups, the proxy requires `Authorization: Bearer <access-token>`.
5. Missing or malformed bearer tokens return `401` with `WWW-Authenticate`.
6. Tokens that validate but do not include the required scopes return `403`.
7. Valid requests are forwarded to the upstream server configured by `endpoint`.

The protected-resource metadata endpoint is:

```text
/.well-known/oauth-protected-resource/mcp/{name}
```

For protected servers, it returns the resource URL, authorization server issuer, supported scopes, and bearer-token support. MCP clients use that metadata to choose the OAuth authorization server and request the correct audience/scope. Anonymous servers return `404` from this metadata endpoint because they do not require OAuth.

## Token Validation

For OIDC-backed groups, the proxy uses the configured issuer to fetch:

- `/.well-known/openid-configuration`
- the JWKS URI advertised by that discovery document

The proxy then validates:

- token signature using the JWKS signing key
- allowed signing algorithm
- issuer
- `exp` and `iat` with configured clock skew
- required `sub`, `aud`, `iss`, `exp`, and `iat` claims
- audience against the configured server `resource`
- required scopes from `scp`, `scope`, or `roles`

The `entra_id` provider uses the same validation path. It exists as a convenience wrapper for Microsoft Entra ID issuer configuration and can derive the issuer from `authority` plus `tenant_id`.

## Microsoft Entra ID Setup

Use Entra ID when the proxy should trust access tokens issued by a Microsoft tenant. The proxy acts like a protected web API: clients acquire an access token for the proxy resource, then send that token to `Authorization: Bearer <access-token>` on MCP requests.

Create one app registration for the proxy API:

1. In Microsoft Entra ID, create an app registration such as `agent-proxy-api`.
2. In **Expose an API**, set the Application ID URI. This value must match each protected server's `resource` value, for example `api://<proxy-api-client-id>` or `https://proxy.example.com/mcp/playwright`.
3. Add a delegated scope such as `mcp.access` for interactive clients.
4. Add an app role with value `mcp.access` if daemon or service clients will use client credentials.
5. Use that same value in `default_required_scopes` or server-level `required_scopes`.

Create one or more client app registrations:

- Browser, desktop, MCP Inspector, VS Code, and Copilot-style clients should use a public client registration with the authorization-code flow and the exact redirect URIs those clients use.
- Service clients should use a confidential client registration with client credentials and a secret or certificate.
- Add API permissions for the proxy API registration and grant the delegated scope or application role.
- Grant admin consent if your tenant requires it.

Configure the proxy with either an explicit issuer:

```yaml
auth:
  provider: entra_id
  issuer: "https://login.microsoftonline.com/<tenant-id>/v2.0"
```

or a tenant ID:

```yaml
auth:
  provider: entra_id
  tenant_id: "<tenant-id>"
```

For delegated user tokens, Entra puts permissions in the `scp` claim. For client-credentials tokens, Entra uses the `roles` claim. The proxy checks both, plus `scope`, so the same `mcp.access` requirement can work for browser users and service clients.

The proxy uses `oid` as the stable principal identifier when Entra includes it, and falls back to `sub` for generic OIDC tokens. That matters because Entra's `sub` can be pairwise per client app, while `oid` identifies the user or service principal within the tenant.

## Credential Handling

Clients send credentials to the proxy with the standard HTTP `Authorization` header. The upstream MCP server does not receive that credential.

When forwarding to upstream, the proxy removes only proxy-local or transport-local headers:

- `Authorization`
- `Host`
- HTTP hop-by-hop headers such as `Connection`, `Transfer-Encoding`, and `Upgrade`

Other request headers pass through to the upstream MCP server, including MCP headers such as `MCP-Session-Id`, `MCP-Protocol-Version`, `Last-Event-ID`, `Accept`, and `Content-Type`.

Response headers are also passed back except HTTP hop-by-hop headers.

## MCP Session Handling

The upstream MCP server owns the actual MCP session. The proxy keeps a protected-session ownership registry so one authenticated principal cannot reuse another principal's MCP session.

On `initialize`, if the upstream response includes `MCP-Session-Id`, the proxy stores:

- server name
- session ID
- issuer
- subject
- client ID when present

The session ID is stored because it is needed to authorize later requests, but it is not logged. Subsequent requests with `MCP-Session-Id` must authenticate as the same `(issuer, subject)` pair. If a different principal tries to reuse the session, the proxy returns `404 Unknown session`.

The proxy validates the bearer token on every protected request. It allows the OAuth client ID to change for the same subject, which supports browser/client refresh flows where the same user gets a token from a different client registration.

The proxy forwards `MCP-Session-Id` to upstream. If upstream returns `404`, the proxy removes its local binding for that session. A successful HTTP `DELETE` does not automatically remove the binding because some MCP clients use `DELETE` for cleanup operations that do not terminate the MCP session.

## Local Development

Start Postgres, Keycloak, and the Playwright MCP server:

```bash
just compose
```

Start the proxy:

```bash
uv run proxy run
```

Compose imports the local Keycloak realm from `resources/keycloak/realm.json`. There is no bootstrap script. The realm includes permissive local OAuth clients with wildcard redirect URIs and web origins so browser tools, VS Code/Copilot, and inspector-style clients can complete callbacks from any local development origin.

Local Keycloak details:

- realm: `agent-proxy`
- admin console: `admin` / `admin`
- public browser client: `mcp-inspector`
- VS Code / Copilot client: `aebc6443-996d-45c2-90f0-388ff96faa56`
- service client: `mcp-tester`
- service client secret: `mcp-tester-secret`
- test user: `admin` / `admin`

## Smoke Test

```bash
TOKEN=$(curl -s \
  -X POST http://localhost:8080/realms/agent-proxy/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials' \
  -d 'client_id=mcp-tester' \
  -d 'client_secret=mcp-tester-secret' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl \
  -X POST http://localhost:8008/mcp/playwright \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke-test","version":"0.1.0"}}}'
```

## Checks

```bash
just lint
just test
```
