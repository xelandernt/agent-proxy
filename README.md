# agent-proxy

An authentication gateway for unauthenticated MCP servers. FastMCP owns MCP
and OAuth; the gateway supplies routing, provider configuration, and a strict
credential boundary in front of each upstream.

The gateway contract is MCP `2026-07-28` only:

- each server is exposed at `/{name}/mcp`;
- there is no `initialize`, `MCP-Session-Id`, GET stream, or DELETE teardown;
- clients and upstream servers are expected to follow the `2026-07-28`
  contract.

## Compatibility

This gateway accepts only the stateless MCP `2026-07-28` protocol. Compatibility
was checked on 7 August 2026:

| Client                | Earliest compatible version | Status and evidence                                                                                                                                                                                                                                                                                       |
|-----------------------|-----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Codex CLI and Desktop | `0.147.0`                   | Supported with `features.mcp_2026_07_28 = true`. [Codex 0.147.0](https://github.com/openai/codex/releases/tag/rust-v0.147.0) adds discovery, multi-round requests, and non-blocking startup; its [implementation](https://github.com/openai/codex/pull/35725) covers the complete client protocol.        |
| OpenCode              | `1.18.8`                    | Supported for modern MCP servers. The [1.18.8 release](https://github.com/anomalyco/opencode/releases/tag/v1.18.8) upgraded compatibility, and its [protocol regression report](https://github.com/anomalyco/opencode/issues/39354) captures the client sending a `2026-07-28` `server/discover` request. |
| GitHub Copilot CLI    | `1.0.79-1` (pre-release)    | Modern discovery is present, but only in the pre-release channel. [Issue #4370](https://github.com/github/copilot-cli/issues/4370) tracks a regression when a legacy server rejects the discovery probe; this gateway implements discovery, so that specific fallback bug does not apply.                 |
| Claude Code           | Not yet announced           | Anthropic says support is still [rolling out](https://claude.com/blog/bringing-mcp-2026-07-28-to-claude); no released Claude Code version has been announced. [Issue #81965](https://github.com/anthropics/claude-code/issues/81965) tracks the missing timeline and per-request behavior.                |

## How it works

MCP servers are managed at runtime from PostgreSQL and stored in a `servers`
table. On startup the gateway loads them, builds one isolated FastMCP proxy
application per server, and mounts it. The configured FastMCP `AuthProvider`
validates the client and publishes its OAuth routes. FastMCP then forwards the
MCP request to the configured upstream.

Servers can be added, updated, and deleted at runtime through the admin API
(`/api/admin/*`) or the admin UI (`/admin`) — changes apply to the running
gateway immediately, with no restart. A brief unmount/remount gap during an
update may drop in-flight requests; the MCP `2026-07-28` protocol is stateless,
so this is acceptable by design.

The upstream HTTP client removes `Authorization`, `Cookie`, and
`Proxy-Authorization`, ignores FastMCP's forwarded auth object, and disables
ambient proxy credentials — unless a server opts into relaying the client's
`Authorization` header (see
[Proxying an already-authenticated server](#proxying-an-already-authenticated-server)).
Modern MCP routing headers and request bodies are preserved.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/) for the convenience commands
- Docker for the Compose example and Keycloak integration suite

## Install

```bash
uv sync --all-extras --frozen
```

FastMCP 4 is beta software. Both `fastmcp` and `fastmcp-slim` are pinned to
`4.0.0b2` so their protocol implementations cannot drift independently.

## Local development example

Start Keycloak and the example MCP server in Docker, then run the gateway
locally with reload enabled:

```bash
just dev
```

The resulting development stack is:

| Process    | Address                             | Runtime                                    |
|------------|-------------------------------------|--------------------------------------------|
| Gateway    | `http://localhost:8008/example/mcp` | Local Python process started by `just dev` |
| Keycloak   | `http://keycloak.localhost:8080`    | Docker container                           |
| MCP server | `http://127.0.0.1:8000/mcp`         | Docker container with a host-local port    |

The example backend in [examples/mcp_server.py](examples/mcp_server.py)
provides typed `echo` and `add` tools. The local gateway uses
`.proxy/config.yaml`; [resources/config.dev.yaml](resources/config.dev.yaml)
is the non-secret reference configuration. Both Compose and the integration
tests import the same
[resources/keycloak/realm.json](resources/keycloak/realm.json).

The `servers` table starts empty; add your first server through the admin UI at
`http://localhost:3000/admin` (the dev configuration enables admin
authentication against the local Keycloak). See
[Adding a new Keycloak-protected server](#adding-a-new-keycloak-protected-server)
for the full walkthrough.

To start only the two Docker dependencies, run `just compose`, then start the
gateway separately with `uv run proxy run --reload`. Stopping `just dev` stops
the local gateway process but leaves its dependencies available for the next
run.

The deterministic smoke-test user is `user` / `password`; the Keycloak admin
login is `admin` / `admin`. These credentials and Keycloak's development mode
are for local use only.

Native MCP clients use Keycloak Dynamic Client Registration automatically: the
realm admits anonymous registrations from localhost hosts, and every token
carries the shared `mcp` audience through the realm's default `mcp-audience`
scope. Browser-based clients cannot use open DCR because Keycloak does not add
the required CORS headers — register a public client for them manually, as the
realm does for the admin UI.

Stop and remove the two dependency containers with:

```bash
just stop
```

### Adding a new Keycloak-protected server

Every server can be protected by the Compose Keycloak. The imported realm is
`agent-proxy` at `http://keycloak.localhost:8080/realms/agent-proxy`; its admin
console is `http://keycloak.localhost:8080/admin` (`admin` / `admin`), and the
deterministic smoke-test user is `user` / `password`.

Keycloak only hands an access token to the gateway when the token's `aud`
claim matches the server's `audience`. The realm's default `mcp-audience`
scope stamps the fixed audience `mcp` into every access token, so every
gateway server in this realm simply sets `audience: mcp` — no per-server
mapper is needed. Native MCP clients registered through Dynamic Client
Registration inherit the realm's default scopes, so their tokens carry the
same audience. Sign in again if you already held a token: the audience is
granted when the token is issued, not before.

Create the server in the admin UI at `http://localhost:3000/admin` (authenticate
as `user` / `password`):

| Field         | Value                                                                 |
|---------------|-----------------------------------------------------------------------|
| Name          | `{name}` — exposed at `http://localhost:8008/{name}/mcp`              |
| Upstream URL  | `http://127.0.0.1:8000/mcp` to reuse the Compose example backend      |
| Auth provider | `keycloak`                                                            |
| `realm_url`   | `http://keycloak.localhost:8080/realms/agent-proxy`                   |
| `audience`    | `mcp` (the realm-wide audience)                                       |

Verify with a native MCP client: connect to `http://localhost:8008/{name}/mcp`
and sign in as `user` / `password`. The client registers itself through DCR
and inherits the realm's default scopes, so its token carries the `mcp`
audience. Once a tool call succeeds, the gateway is proxying authenticated
MCP requests to the upstream.

To serve a genuinely different backend, add a second service to
[compose.yml](compose.yml) modeled on `mcp-server` and point `upstream_url` at
it instead.

### Proxying an already-authenticated server

If your upstream MCP server already authenticates its clients, the gateway can
proxy it without adding any authentication of its own. Choose the `none` auth
provider and enable `forward_client_credentials`:

| Field                        | Value                            |
|------------------------------|----------------------------------|
| Name                         | `{name}` — exposed at `http://localhost:8008/{name}/mcp` |
| Upstream URL                 | the URL of your authenticated server |
| Auth provider                | `none`                           |
| Forward client credentials   | `true` (default `false`)         |

With provider `none` the gateway publishes no OAuth routes and verifies no
tokens: every request reaches the upstream, and the upstream's own responses —
including its 401s — are relayed back unchanged. With `forward_client_credentials`
enabled, the client's `Authorization` header is passed through to the upstream
instead of being stripped, so MCP clients keep using the token they already
have for your server. The discovery document advertises such servers with
`"auth": "none"`.

This mode is a trust decision, not a security one: the gateway adds no identity
boundary, and `forward_client_credentials` is rejected for every other provider
so a gateway-issued token can never leak upstream. Only use it when the
upstream's own authentication protects the tools.

## Configure

Copy [resources/config.example.yaml](resources/config.example.yaml) to
`.proxy/config.yaml`, then edit it for your environment:

```yaml
public_base_url: https://mcp.example.com

# Required: server configuration and usage tracing live in PostgreSQL.
database:
  url: postgresql+asyncpg://proxy:proxy@localhost:5432/proxy

# Optional: the identity provider that may log in to the admin API and UI.
# Any user authenticated against this provider is an administrator. When
# omitted, the admin interface returns HTTP 503.
admin:
  auth:
    provider: keycloak
    realm_url: https://identity.example.com/realms/agents
    client_id: agent-proxy-admin-ui
```

MCP servers are no longer configured in YAML. They are created at runtime
through the admin API (`/api/admin/servers`) or the admin UI at `/admin`:

- `POST /api/admin/servers` — create and live-mount a server
- `PUT /api/admin/servers/{name}` — replace a server's definition live
- `DELETE /api/admin/servers/{name}` — unmount and delete a server
- `GET /api/admin/servers` — list mounted servers
- `GET /api/admin/auth-schema` — JSON Schema for every supported auth provider

A server definition carries a `name` (immutable, unique), `description`,
`upstream_url`, `verify_upstream_tls`, an optional
`forward_client_credentials` flag, and an `auth` provider configuration.
The public endpoint for a server named `calendar` is
`https://mcp.example.com/calendar/mcp`. The gateway supplies
`https://mcp.example.com/calendar` as the provider's `base_url`; it is not a
configurable authentication field.

`auth` is a discriminated union of fully typed provider configurations.
Provider-specific required fields and secrets are validated on every write, so
the API cannot accept a configuration that would fail at mount time. Supported
provider discriminators are:

| Integration           | `provider`    |
|-----------------------|---------------|
| Auth0                 | `auth0`       |
| WorkOS AuthKit        | `authkit`     |
| AWS Cognito           | `aws-cognito` |
| Microsoft Entra ID    | `azure`       |
| Descope               | `descope`     |
| Discord               | `discord`     |
| GitHub                | `github`      |
| Google                | `google`      |
| Hugging Face          | `huggingface` |
| JWT/JWKS verification | `jwt`         |
| Keycloak              | `keycloak`    |
| No authentication     | `none`        |
| OCI IAM               | `oci`         |
| PropelAuth            | `propelauth`  |
| Scalekit              | `scalekit`    |
| Supabase              | `supabase`    |
| WorkOS                | `workos`      |

See the [FastMCP Keycloak integration](https://gofastmcp.com/integrations/keycloak)
and the corresponding FastMCP integration guide for any other provider's
fields and OAuth behavior. Keycloak 26.6.0 or newer supports the remote OAuth
pattern with Dynamic Client Registration, so native interactive clients can
register without manual client configuration. Other providers may require a
gateway OAuth client as documented by FastMCP.

Configuration is loaded from `.proxy/config.yaml`. Set `PROXY_CONFIG_FILE` to
use another file. Environment variables use the `PROXY__` prefix and `__` as
the nested delimiter. Treat configuration files and environment variables as
sensitive because provider credentials and Logfire tokens may be stored there.

Logfire request tracing and basic system metrics remain integrated through
FastAPI. Telemetry is sent only when a write token is present:

```yaml
logfire:
  token: your-logfire-write-token
  environment: production
  service_name: agent-proxy
```

The token can instead be supplied as `PROXY__LOGFIRE__TOKEN`. Without a token,
Logfire remains local and does not export telemetry.

### Admin authentication and the browser login flow

The admin identity boundary uses an explicit admin provider contract:
`keycloak` for browser sign-in, `jwt` for pasted tokens, or `static` for a
gateway-owned username and password. Every
protected admin endpoint validates the session cookie or
`Authorization: Bearer <token>` through the provider.

For `keycloak` the admin UI runs the standard Authorization Code Flow with
PKCE **directly against the realm**: the login screen reads the realm's
authorization server metadata and redirects the browser to Keycloak, where the
user authenticates as a pre-registered **public** client (no client secret).
The UI exchanges the resulting code for the realm-issued access token and
attaches it to admin API calls, which the gateway verifies against the realm's
JWKS — the same token is accepted whether it arrives via the browser flow or
is pasted in manually.

```yaml
admin:
  auth:
    provider: keycloak
    realm_url: https://identity.example.com/realms/agents
    # Required: public client the admin UI uses for the browser sign-in flow.
    # Register {ui-origin}/admin/callback as a redirect URI on this client and
    # enable PKCE (S256). The gateway rejects the config without it — without
    # an audience check it would accept any token from the realm.
    client_id: agent-proxy-admin-ui
```

The `jwt` provider has no browser sign-in. Obtain an access token from the
identity provider and paste it into the admin login screen. After verification,
the gateway stores the token in an HttpOnly session cookie; a 401 returns the
browser to the login screen.

For the browser flow, register the UI's redirect URI —
`{ui-origin}/admin/callback` — with the provider, and include the UI origin in
`cors_origins`.

Alternatively, a plain username/password admin account can be configured
instead of an OAuth provider. The gateway checks the credentials at
`POST /api/admin/login` (constant-time comparison) and signs a short-lived
HS256 JWT with `jwt_secret`; the gateway stores it in the same HttpOnly session
cookie used by the other admin flows:

```yaml
admin:
  auth:
    provider: static
    # username: user          # defaults to "user"
    # password: change-me     # defaults to "password"
    # 32+ random bytes; keep it secret — anyone with this secret can forge
    # admin tokens. Defaults to a public development-only value: always set
    # it explicitly.
    jwt_secret: ${ADMIN_JWT_SECRET}
    # token_ttl_seconds: 3600
```

### Usage tracing

The gateway records request volumes per MCP server, tool, and client app, and
exposes them in the UI (server detail page, filterable by time window). The
required PostgreSQL database doubles as usage storage:

```yaml
database:
  url: postgresql+asyncpg://proxy:proxy@localhost:5432/proxy
```

Tables are created automatically on startup. Only authenticated requests are
recorded (unauthenticated attempts are skipped), and only request counts,
client identifiers, and response status codes are stored — never request
payloads.

Generate the current JSON Schema with:

```bash
just config-schema
```

## Run

```bash
uv run proxy run
```

The listener defaults to `127.0.0.1:8008`. Override it in the config or with
CLI flags:

```bash
uv run proxy run --host 0.0.0.0 --port 8008
```

For local reload:

```bash
just dev
```

FastMCP mounts each provider's operational OAuth routes beneath the server
prefix, alongside `/{name}/mcp`. Standards-defined discovery routes remain at
the root, for example
`/.well-known/oauth-protected-resource/{name}/mcp`. Connect clients to the MCP
URL and let the provider's protected-resource challenge drive authentication.

## Test

```bash
just test
just typecheck
just lint
```

The integration suite exercises FastMCP auth, named routing, lifecycle
composition, the credential firewall, and a real Keycloak 26.6 instance.

## License

See [LICENSE](LICENSE).
