# Implementation Plan: Proxy Integration Tests With Testcontainers

## Overview

Add Docker-backed pytest coverage for the FastAPI MCP proxy using Testcontainers Python. The tests should exercise the real external boundaries that matter for this repository: Postgres-backed protected-session storage, OIDC metadata/JWKS/token validation against Keycloak, forwarding to the Playwright MCP container running as HTTP MCP, and local OAuth client-registration expectations. The goal is not to replace focused unit tests; it is to make the local proxy contract executable without relying on a pre-running `compose.yml` stack or fixed localhost ports.

## Current Baseline

- The repository currently has pytest, pytest-asyncio, and testcontainers in the dev dependency group.
- There is no source test suite checked in under `tests/`; only a stale `tests/__pycache__` artifact exists.
- `compose.yml` defines the intended external services: Postgres 17, Keycloak 26.4 importing `resources/keycloak/realm.json`, and `mcr.microsoft.com/playwright/mcp`.
- `create_app(config=...)` already supports test-specific config injection.
- The proxy session registry creates its SQLAlchemy tables on app startup and disposes the engine on shutdown.

## Architecture Decisions

- Use Testcontainers fixtures instead of the local Compose stack so tests do not require fixed host ports.
- Keep expensive Docker services session-scoped; keep app instances, database cleanup, and request clients function-scoped.
- Use Testcontainers mapped host/port helpers for every service endpoint.
- Use explicit readiness checks for each container: Postgres connection readiness, Keycloak health or metadata readiness, and Playwright MCP HTTP readiness.
- Test the proxy with `niquests.Session(app=..., base_url=...)` so the test client uses the same HTTP stack as the proxy code, while the proxy itself talks to Docker-backed Keycloak/Postgres/upstream endpoints over mapped URLs.
- Run the upstream exactly as `compose.yml` does: `mcr.microsoft.com/playwright/mcp` with `node /app/cli.js --headless --browser chromium --no-sandbox --port 8931 --host 0.0.0.0`, exposed through the mapped container port and addressed at `/mcp`.
- Keep the implementation a pure MCP proxy: tests should assert forwarding, auth enforcement, header filtering, metadata, and session ownership rather than adding client-specific behavior.

## Task List

### Phase 1: Test Harness Foundation

## Task 1: Establish the pytest integration layout

**Description:** Create the test package structure and pytest conventions for Docker-backed integration tests. This task should add the minimum scaffolding needed for later Testcontainers fixtures without starting any service yet.

**Acceptance criteria:**
- [ ] `tests/conftest.py` and `tests/integration/conftest.py` exist with clear fixture boundaries.
- [ ] Integration tests can be selected independently with a marker or path.
- [ ] `pytest-asyncio` is configured for async fixtures and async tests.
- [ ] Proxy HTTP requests in tests use `niquests`; no `httpx` test client or dependency is introduced.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration -q`
- [ ] Full suite still runs: `uv run pytest -q`

**Dependencies:** None

**Files likely touched:**
- `pyproject.toml`
- `tests/conftest.py`
- `tests/integration/conftest.py`

**Estimated scope:** Small: 2-3 files

## Task 2: Add container wrapper fixtures

**Description:** Add reusable Testcontainers fixtures for Postgres, Keycloak, and the Playwright MCP HTTP server. The fixtures should expose typed endpoint helpers and hide image names, exposed ports, environment variables, import mounts, startup commands, and readiness checks.

**Acceptance criteria:**
- [ ] Postgres uses `PostgresContainer` and exposes a SQLAlchemy asyncpg-compatible connection config.
- [ ] Keycloak uses a small custom `DockerContainer` wrapper that imports `resources/keycloak/realm.json` and waits for realm metadata to respond.
- [ ] The upstream MCP service uses `mcr.microsoft.com/playwright/mcp` with the same HTTP MCP command as `compose.yml`.
- [ ] The Playwright MCP fixture exposes a mapped endpoint URL ending in `/mcp` and uses HTTP or log readiness based on the actual container behavior.

**Verification:**
- [ ] Narrow fixture smoke passes: `uv run pytest tests/integration/test_containers.py -q`
- [ ] No fixture hard-codes host ports.

**Dependencies:** Task 1

**Files likely touched:**
- `tests/integration/conftest.py`
- `tests/integration/containers.py`
- `tests/integration/test_containers.py`

**Estimated scope:** Medium: 3 files

### Checkpoint: Harness

- [ ] Docker-backed fixture smoke tests pass.
- [ ] Container teardown is automatic through fixture context managers.
- [ ] No fixed host ports or arbitrary sleeps were introduced.

### Phase 2: Proxy App Wiring

## Task 3: Build test-specific proxy config fixtures

**Description:** Add fixtures that construct `proxy.settings.Config` objects from container endpoints. These fixtures should produce both an anonymous group and a protected OIDC group so later tests can exercise metadata, auth, forwarding, and session behavior without reading `.proxy/config.yaml`.

**Acceptance criteria:**
- [ ] The protected config points OIDC `issuer` at the mapped Keycloak realm URL.
- [ ] The protected server `endpoint` points at the mapped Playwright MCP `/mcp` endpoint.
- [ ] The protected server `resource` and required scope match the imported realm's `mcp.access` audience/scope contract.

**Verification:**
- [ ] App startup succeeds against the Testcontainers Postgres database.
- [ ] Metadata endpoint returns protected-resource metadata for the protected server.
- [ ] Anonymous metadata endpoint returns `404`.

**Dependencies:** Task 2

**Files likely touched:**
- `tests/integration/conftest.py`
- `tests/integration/test_metadata.py`

**Estimated scope:** Medium: 2-3 files

## Task 4: Add OAuth token helper fixtures

**Description:** Add a helper for obtaining access tokens from the Testcontainers Keycloak realm. The first supported path should use the checked-in `local-mcp-client` public client and test user credentials from the imported realm.

**Acceptance criteria:**
- [ ] Token helper requests a bearer token from the mapped Keycloak token endpoint.
- [ ] The helper asserts the token includes `mcp.access` and an audience accepted by the test proxy config.
- [ ] A negative helper path can request a token that fails proxy authorization, either by missing scope or by targeting a mismatched audience.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration/test_auth.py -q`
- [ ] Invalid or missing bearer token tests return `401` or `403` with `WWW-Authenticate` where appropriate.

**Dependencies:** Task 3

**Files likely touched:**
- `tests/integration/conftest.py`
- `tests/integration/oauth.py`
- `tests/integration/test_auth.py`

**Estimated scope:** Medium: 2-3 files

### Checkpoint: Auth

- [ ] Protected metadata advertises the mapped Keycloak issuer and `mcp.access`.
- [ ] Valid Keycloak tokens are accepted by the proxy.
- [ ] Missing, malformed, wrong-audience, and missing-scope requests fail before forwarding.

### Phase 3: End-to-End Proxy Behavior

## Task 5: Test authenticated MCP initialize forwarding

**Description:** Add an end-to-end test that acquires a real Keycloak token, calls `POST /mcp/{name}` with a JSON-RPC `initialize` request, and verifies the proxy forwards to the Playwright MCP HTTP container.

**Acceptance criteria:**
- [ ] A valid bearer token can initialize an MCP session through the proxy.
- [ ] The response status, body shape, and `MCP-Session-Id` behavior match the Playwright MCP HTTP response.
- [ ] The same session can make a follow-up MCP request, such as `tools/list`, through the proxy.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration/test_mcp_proxy.py -q -k initialize`
- [ ] The test fails if the proxy cannot reach Keycloak, Postgres, or the Playwright MCP container.

**Dependencies:** Task 4

**Files likely touched:**
- `tests/integration/test_mcp_proxy.py`
- `tests/integration/conftest.py`

**Estimated scope:** Medium: 2 files

## Task 6: Test protected session ownership

**Description:** Add integration tests for the proxy-owned session binding rules using the real Postgres registry. These tests should cover binding on `initialize`, reuse by the same principal, rejection for a different principal, rebind after local registry loss, and removal on successful forwarded `DELETE`.

**Acceptance criteria:**
- [ ] `initialize` stores a binding in Postgres for the authenticated principal.
- [ ] A later request with the same `MCP-Session-Id` succeeds for the same subject and fails with `404 Unknown session` for a different subject.
- [ ] A successful forwarded `DELETE` removes the local binding.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration/test_session_ownership.py -q`
- [ ] Database state assertions confirm bindings are created and removed.

**Dependencies:** Task 5

**Files likely touched:**
- `tests/integration/test_session_ownership.py`
- `tests/integration/conftest.py`

**Estimated scope:** Medium: 2 files

## Task 7: Test upstream error and recovery paths

**Description:** Add proxy integration tests for cases where the configured Playwright MCP upstream endpoint is unavailable or a Playwright-owned session is no longer accepted. These tests should assert the proxy's observable behavior and the corresponding registry cleanup while keeping the normal success path on the real Playwright MCP container.

**Acceptance criteria:**
- [ ] An unreachable upstream returns `502` with the configured server name in the error detail.
- [ ] A protected request whose Playwright MCP session is rejected upstream removes the local session binding.
- [ ] Non-event-stream responses close upstream response handles without leaking sessions.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration/test_upstream_failures.py -q`
- [ ] The full integration suite still passes when tests run in random order.

**Dependencies:** Task 6

**Files likely touched:**
- `tests/integration/test_upstream_failures.py`
- `tests/integration/conftest.py`

**Estimated scope:** Medium: 2 files

### Checkpoint: Proxy Contract

- [ ] Real token-to-proxy-to-upstream initialize flow passes.
- [ ] Postgres-backed protected-session rules pass.
- [ ] Failure paths return the documented status codes and clean local state.

### Phase 4: OAuth Client Registration Coverage

## Task 8: Add Keycloak DCR regression tests

**Description:** Add tests around the local Keycloak dynamic client registration contract imported from `resources/keycloak/realm.json`. These tests should verify that anonymous DCR works with the realm policy and that the registration payload does not supply a caller-chosen `client_id`.

**Acceptance criteria:**
- [ ] Anonymous DCR against mapped Keycloak creates a client when the payload omits `client_id`.
- [ ] The created client can request the proxy-advertised `mcp.access` scope according to realm policy.
- [ ] The test documents the expected rejection mode when DCR is sent with a disallowed host or invalid scope.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration/test_keycloak_dcr.py -q`
- [ ] DCR tests do not depend on a pre-existing local Keycloak volume.

**Dependencies:** Task 4

**Files likely touched:**
- `tests/integration/test_keycloak_dcr.py`
- `tests/integration/oauth.py`

**Estimated scope:** Medium: 2 files

## Task 9: Add a documented full smoke command

**Description:** Add a small documented command or pytest marker that runs the expensive Docker-backed contract suite. This should be the command future changes use when auth, proxy routing, session ownership, Keycloak realm import, or container wiring changes.

**Acceptance criteria:**
- [ ] README or developer docs name the integration command and Docker prerequisite.
- [ ] The command runs the Testcontainers suite without requiring `just compose`.
- [ ] Existing `just test` remains valid for all tests.

**Verification:**
- [ ] Tests pass: `uv run pytest tests/integration -q`
- [ ] Broader checks pass: `just test`

**Dependencies:** Tasks 5-8

**Files likely touched:**
- `README.md`
- `justfile`
- `pyproject.toml`

**Estimated scope:** Small: 2-3 files

### Checkpoint: Complete

- [ ] `uv run pytest tests/integration -q` passes with Docker running.
- [ ] `uv run pytest -q` passes.
- [ ] `just lint` passes.
- [ ] No tests depend on fixed localhost ports or a running Compose stack.
- [ ] The plan's auth-and-call smoke path is covered by automated tests.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Keycloak startup is slow or readiness is flaky. | High | Use a session-scoped container and wait on real realm metadata or health endpoints, not sleeps. |
| Keycloak issuer URLs can mismatch dynamic mapped ports. | High | Build proxy config from the same mapped realm URL used to request tokens and discovery metadata. |
| The realm's fixed audience mapper uses `http://localhost:8008/mcp/playwright`. | Medium | Set the test protected server `resource` or `accepted_audiences` to match the imported realm audience while still using mapped endpoints for actual network calls. |
| Playwright MCP image startup is expensive. | Medium | Keep it session-scoped and run the forwarding/session suite against that one container instead of starting substitutes per test. |
| Session tests may share Postgres state across tests. | Medium | Keep the container session-scoped but truncate `mcp_session_bindings` or create unique server/session IDs per function. |
| CI may not have Docker available. | Medium | Mark integration tests clearly and document Docker as a prerequisite; do not silently skip locally unless the project chooses an explicit skip policy. |

## Parallelization Opportunities

- Tasks 3 and 4 can be split after Task 2 defines container endpoints.
- Tasks 6 and 7 can be developed in parallel after Task 5 establishes the authenticated initialize path.
- Task 8 can be developed in parallel with Tasks 5-7 because it exercises Keycloak realm behavior rather than proxy request forwarding.

## Open Questions

- Should Docker-backed integration tests always run under `just test`, or should they require an explicit marker in CI to avoid image-pull cost?
- Should the stale `tests/__pycache__` directory be removed as part of Task 1 cleanup?
