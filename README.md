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

database:
  address: 127.0.0.1
  port: 5432
  username: postgres
  password: postgres
  database: agent_proxy
  sslmode: disable

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

Each group shares one auth provider. Servers in protected groups must configure `resource`; this is the OAuth protected-resource identifier advertised to MCP clients and should match the MCP server URL or origin clients connect to. Access-token audiences are matched against `resource` plus any server-level `accepted_audiences`. Use `accepted_audiences` when the identity provider emits a different audience, such as an Entra ID Application ID URI.

`authorization_scopes` controls what the proxy advertises to OAuth clients in protected-resource metadata. `required_scopes` controls what the proxy enforces on incoming access tokens. If `authorization_scopes` is unset, it defaults to `required_scopes`. Server-level `authorization_scopes` and `required_scopes` inherit from `default_authorization_scopes` and `default_required_scopes`.

`database.url` is derived from those top-level database fields, so application code can use one DSN while config stays split into explicit parts.

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

MCP OAuth clients then discover authorization-server metadata from the advertised issuer with RFC 8414, usually at `/.well-known/oauth-authorization-server/...`. Some MCP clients require RFC 8414 metadata; if your identity provider only exposes OpenID Connect discovery, those clients can fail before login starts.

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
2. In **Expose an API**, set the Application ID URI, for example `api://<proxy-api-client-id>`.
3. Add a delegated scope such as `mcp.access` for interactive clients.
4. Add an app role with value `mcp.access` if daemon or service clients will use client credentials.
5. Configure the MCP server's `resource` as the MCP URL clients connect to, and add the Entra Application ID URI to `accepted_audiences`.
6. Use the delegated scope or app-role value in `default_required_scopes` or server-level `required_scopes`.

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

Example server config for Entra ID:

```yaml
servers:
  - name: playwright-azure
    endpoint: "http://localhost:8931/mcp"
    resource: "http://localhost:8008/mcp/playwright-azure"
    authorization_scopes:
      - "openid"
      - "profile"
    accepted_audiences:
      - "api://<proxy-api-client-id>"
```

For delegated user tokens, Entra puts permissions in the `scp` claim. For client-credentials tokens, Entra uses the `roles` claim. The proxy checks both, plus `scope`, so the same `mcp.access` requirement can work for browser users and service clients.

The proxy uses `oid` as the stable principal identifier when Entra includes it, and falls back to `sub` for generic OIDC tokens. That matters because Entra's `sub` can be pairwise per client app, while `oid` identifies the user or service principal within the tenant.

## Credential Handling

Clients send credentials to the proxy with the standard HTTP `Authorization` header. The upstream MCP server does not receive that credential.

When forwarding to upstream, the proxy removes only proxy-local or transport-local headers:

- `Authorization`
- `Host`
- Configured HTTP hop-by-hop headers (default: `Connection`, `Transfer-Encoding`, `Upgrade`, etc.)

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

The proxy forwards `MCP-Session-Id` to upstream. If upstream returns `404`, the proxy removes its local binding for that session. A successful HTTP `DELETE` removes the local session binding, as the upstream has accepted session termination.

If the proxy loses its local binding but the upstream server still accepts the `MCP-Session-Id`, the proxy re-binds the session to the authenticated principal on the next successful request. This covers proxy restarts or local registry loss without allowing one principal to steal another principal's live session.

## Local Development

Start Postgres, Keycloak, and the Playwright MCP server:

```bash
just compose
```

Start the proxy:

```bash
uv run proxy run
```

Compose imports the local Keycloak realm from `resources/keycloak/realm.json`. There is no bootstrap script. The realm includes two pre-created public OAuth clients and supports anonymous dynamic client registration.

Local Keycloak details:

- realm: `agent-proxy`
- admin console: `admin` / `admin`
- static local client: `local-mcp-client` (use when a client needs a known `client_id`)
- VS Code / Copilot compatible client: `aebc6443-996d-45c2-90f0-388ff96faa56`
- test user: `admin` / `admin`
- Keycloak version pins at `26.4` for RFC 8414 root-level metadata endpoint support.
- The `mcp.access` client scope includes an audience mapper that emits `http://localhost:8008/mcp/playwright`.
- Anonymous dynamic client registration is enabled for local development with a `Trusted Hosts` policy that allows `localhost`, `127.0.0.1`, and `opencode.ai`, plus a `Max Clients Limit` policy. Do not copy this local DCR policy to production.

Client harness requirements:

- Codex: configure the MCP server URL as `http://localhost:8008/mcp/playwright`, then run `codex mcp login playwright`. The OAuth provider must support dynamic client registration and allow the client to request the proxy-advertised `mcp.access` scope.
- OpenCode: configure a remote MCP server named `playwright` with URL `http://localhost:8008/mcp/playwright`, then run `opencode mcp auth playwright`. The OAuth provider must support dynamic client registration and allow OpenCode's registered client URLs, including `https://opencode.ai`.
- Both clients require RFC 8414 authorization-server metadata from the OAuth provider and proxy protected-resource metadata from `/.well-known/oauth-protected-resource/mcp/playwright`.

If a client reports:

```text
Policy 'Trusted Hosts' rejected request to client-registration service. Details: Host not trusted.
```

then Keycloak is rejecting dynamic client registration. If you already started the Compose stack before the local realm included DCR settings, recreate the Keycloak container and volume so the updated realm is imported.

If a client reports:

```text
Policy 'Allowed Client Scopes' rejected request to client-registration service. Details: Not permitted to use specified clientScope
```

then Keycloak is rejecting the scopes requested during dynamic client registration. The local development realm should not include the anonymous `Allowed Client Scopes` DCR policy; remove that policy from the running realm or recreate the Keycloak container and volume so the updated realm is imported.

## Smoke Test

After an MCP client completes OAuth, send the issued bearer token to the proxy:

```bash
TOKEN="<access-token>"

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
