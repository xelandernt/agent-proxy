# agent-proxy

Agentic gateway / proxy for agents and MCP.

## What it does

- exposes named MCP HTTP servers behind `/mcp/{name}`
- groups MCP servers so each group owns one auth provider
- supports pluggable auth providers per group, with `disabled` and `entra_id` implemented
- publishes MCP OAuth protected-resource metadata per server
- ships a demo MCP HTTP server you can run with Docker Compose

## Configuration

Configuration is loaded with Pydantic Settings from:

1. environment variables prefixed with `PROXY__`
2. a YAML file at `.proxy/config.yaml`
3. or a custom YAML path via `PROXY_CONFIG_FILE`

The grouped MCP config looks like this:

```yaml
host:
  address: 127.0.0.1
  port: 8008

security:
  trusted_origins:
    - "http://localhost:3000"

mcp:
  groups:
    - name: internal-tools
      auth:
        provider: entra_id
        tenant_id: "your-tenant-id"
      default_required_scopes:
        - "mcp.access"
      servers:
        - name: jira
          resource: "https://proxy.example.com/mcp/jira"
          endpoint: "http://jira-mcp:9001/mcp"
        - name: github
          resource: "https://proxy.example.com/mcp/github"
          endpoint: "http://github-mcp:9002/mcp"
          required_scopes:
            - "github.mcp.access"

    - name: local-demo
      auth:
        provider: disabled
      servers:
        - name: demo
          endpoint: "http://demo-mcp:9001/mcp"
```

`required_scopes` is inherited from the group when omitted. If a server sets `required_scopes`, that value replaces the group default for that server.

## Auth providers

### `disabled`

Anonymous passthrough. The proxy does not challenge the client, and disabled servers do not expose MCP protected-resource metadata.

### `entra_id`

Azure Entra ID bearer-token validation using OIDC discovery and JWKS. The proxy validates:

- issuer
- audience against the configured MCP server `resource`
- expiry / issued-at / signature
- configured scopes from either `scp` or `roles`

The proxy strips the client `Authorization` header before forwarding upstream.

## MCP session forwarding

The proxy forwards `MCP-Session-Id` transparently and keeps a proxy-side ownership registry for protected groups. Once a protected session is initialized, subsequent requests for that session must come from the same authenticated principal (`issuer`, `sub`, `client_id`) or the proxy returns `404 Unknown session`.

The registry is process-local. If you run multiple proxy workers or replicas, you need shared session state or sticky routing so a protected session stays on the same proxy instance that recorded it.

## Docker Compose demo

Start the proxy plus the demo backend:

```bash
docker compose up --build
```

By default the compose demo uses `examples/proxy.compose.yaml`, which defines one disabled-auth group containing the `demo` server. That makes the backend available at:

```text
http://localhost:8008/mcp/demo
```

If you want Entra authentication in compose, point `PROXY_CONFIG_FILE` at your own grouped YAML config:

```bash
export PROXY_CONFIG_FILE=/app/.proxy/config.yaml
docker compose up --build
```

Protected-resource metadata for a protected server is available at:

```text
http://localhost:8008/.well-known/oauth-protected-resource/mcp/jira
```

Disabled/public servers return `404` on that path because they are not protected OAuth resources.

## MCP Inspector with Entra ID

`just inspector` starts a plain MCP Inspector instance. For protected `entra_id` servers, the inspector itself must already be registered as an OAuth client in Microsoft Entra ID.

The proxy can tell the inspector **which** authorization server and scopes to use, but it cannot provide the inspector's own OAuth client registration. If the inspector has no preregistered client information, it falls back to dynamic client registration, and Entra ID does not support that flow.

To use the inspector against a protected server:

1. Register the inspector as an OAuth client in Entra ID.
2. Add these redirect URIs to that client:
   - `http://localhost:6274/oauth/callback`
   - `http://localhost:6274/oauth/callback/debug`
3. In the inspector UI, enter the server URL and the preregistered OAuth client ID in the connection settings. Add the client secret only if your Entra app requires one.
4. Use `mcp.access` as the requested scope unless your server config overrides it.

Also make sure each protected server's `resource` value matches the real audience Entra will place into the access token. The example values in this repository are placeholders.

## Demo request

Without auth enabled for the `demo` group:

```bash
curl \
  -X POST http://localhost:8008/mcp/demo \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"demo","version":"0.1.0"}}}'
```
