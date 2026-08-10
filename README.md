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

Each configured server becomes an isolated FastMCP proxy application. The
configured FastMCP `AuthProvider` validates the client and publishes its OAuth
routes. FastMCP then forwards the MCP request to the configured upstream.

The upstream HTTP client removes `Authorization`, `Cookie`, and
`Proxy-Authorization`, ignores FastMCP's forwarded auth object, and disables
ambient proxy credentials. Modern MCP routing headers and request bodies are
preserved.

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

To start only the two Docker dependencies, run `just compose`, then start the
gateway separately with `uv run proxy run --reload`. Stopping `just dev` stops
the local gateway process but leaves its dependencies available for the next
run.

The deterministic smoke-test user is `example` / `example`; the Keycloak admin
login is `admin` / `admin`. These credentials and Keycloak's development mode
are for local use only.

Native MCP clients use Keycloak Dynamic Client Registration automatically.
Browser-based MCP Inspector cannot use open DCR because Keycloak does not add
the required CORS headers. In Inspector's OAuth 2.0 settings, use Client ID
`mcp-inspector` and leave Client Secret empty. The shared realm registers its
localhost callback URLs, web origin, and required PKCE S256 policy.

Stop and remove the two dependency containers with:

```bash
just stop
```

## Configure

Copy [resources/config.example.yaml](resources/config.example.yaml) to
`.proxy/config.yaml`, then edit it for your provider and upstream:

```yaml
public_base_url: https://mcp.example.com

servers:
  - name: calendar
    upstream_url: http://calendar.internal:8000/mcp
    auth:
      provider: keycloak
      realm_url: https://identity.example.com/realms/agents
      audience: https://mcp.example.com/calendar/mcp
      required_scopes:
        - openid
```

The public endpoint in this example is
`https://mcp.example.com/calendar/mcp`. The gateway supplies
`https://mcp.example.com/calendar` as the provider's `base_url`; it is not a
configurable authentication field.

`auth` is a discriminated union of fully typed provider configurations.
Provider-specific required fields and secrets are validated while loading the
gateway configuration, before any application is constructed. Supported
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
