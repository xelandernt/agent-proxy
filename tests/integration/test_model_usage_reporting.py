from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text

from proxy.api_keys.models import ApiKeyRecord
from proxy.app.dependencies import get_user_service
from proxy.app.main import create_app
from proxy.app.model_usage.models import ModelUsageEvent
from proxy.app.model_usage.repository import ModelUsageFilters, ModelUsageRepository
from proxy.app.users.repository import UserRepository
from proxy.app.users.schemas import UserPrincipal, UserView
from proxy.app.users.service import UserAuthenticationError
from proxy.database import create_all_tables, create_engine, create_session_factory
from proxy.settings import GatewayConfig

USER_EXPLAIN = "EXPLAIN (FORMAT JSON) SELECT count(*) FROM model_usage_events WHERE user_id = :value AND ts >= :start AND ts < :end"
KEY_EXPLAIN = "EXPLAIN (FORMAT JSON) SELECT count(*) FROM model_usage_events WHERE api_key_id = :value AND ts >= :start AND ts < :end"
MODEL_EXPLAIN = "EXPLAIN (FORMAT JSON) SELECT count(*) FROM model_usage_events WHERE model_name = :value AND ts >= :start AND ts < :end"


class ReportingUserService:
    def __init__(self, users: dict[str, UserView]) -> None:
        self._users = users

    async def authenticate(self, token: str) -> UserView:
        try:
            return self._users[token]
        except KeyError as error:
            raise UserAuthenticationError("Invalid or expired bearer token.") from error


def _config(postgresql: dict[str, object]) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "public_base_url": "https://gateway.example",
            "postgresql": postgresql,
            "admin": {
                "auth": {
                    "provider": "static",
                    "username": "admin",
                    "password": "secret",
                    "jwt_secret": "reporting-test-signing-secret-at-least-32-bytes",
                }
            },
            "user": {
                "auth": {
                    "provider": "jwt",
                    "public_key": "test-user-auth-secret",
                    "algorithm": "HS256",
                }
            },
            "model_gateway": {
                "credential_encryption_key": (
                    "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="
                )
            },
        }
    )


async def _seed(database_url: str) -> tuple[dict[str, UserView], dict[str, object]]:
    engine = create_engine(database_url)
    await create_all_tables(engine)
    factory = create_session_factory(engine)
    users = UserRepository(factory)
    first = await users.upsert(
        UserPrincipal(
            issuer="https://identity.example",
            subject="first",
            email="first@example.com",
            display_name="First User",
        )
    )
    second = await users.upsert(
        UserPrincipal(
            issuer="https://identity.example",
            subject="second",
            email="second@example.com",
            display_name="Second User",
        )
    )
    now = datetime(2026, 8, 18, 12, 30, tzinfo=UTC)
    first_key = ApiKeyRecord(
        user_id=first.id,
        name="First active",
        prefix="sk_first",
        digest="a" * 64,
        created_at=now,
        last_used_at=now,
        revoked_at=None,
    )
    revoked_key = ApiKeyRecord(
        user_id=first.id,
        name="First revoked",
        prefix="sk_old",
        digest="b" * 64,
        created_at=now,
        last_used_at=now,
        revoked_at=now,
    )
    second_key = ApiKeyRecord(
        user_id=second.id,
        name="Second active",
        prefix="sk_second",
        digest="c" * 64,
        created_at=now,
        last_used_at=now,
        revoked_at=None,
    )
    async with factory() as session:
        session.add_all([first_key, revoked_key, second_key])
        await session.flush()
        session.add_all(
            [
                ModelUsageEvent(
                    user_id=first.id,
                    api_key_id=first_key.id,
                    model_name="alpha",
                    provider="openai",
                    status_code=200,
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    cost_usd=Decimal("0.100000000001"),
                    duration_ms=20,
                    error_type=None,
                    streaming=False,
                    ts=now,
                ),
                ModelUsageEvent(
                    user_id=first.id,
                    api_key_id=revoked_key.id,
                    model_name="beta-deleted",
                    provider="anthropic",
                    status_code=502,
                    input_tokens=None,
                    output_tokens=None,
                    total_tokens=None,
                    cost_usd=None,
                    duration_ms=30,
                    error_type="upstream_error",
                    streaming=True,
                    ts=now + timedelta(minutes=1),
                ),
                ModelUsageEvent(
                    user_id=second.id,
                    api_key_id=second_key.id,
                    model_name="alpha",
                    provider="openai",
                    status_code=200,
                    input_tokens=4,
                    output_tokens=6,
                    total_tokens=10,
                    cost_usd=Decimal(0),
                    duration_ms=10,
                    error_type=None,
                    streaming=False,
                    ts=now,
                ),
            ]
        )
        await session.commit()
    await engine.dispose()
    return (
        {
            "first-token": UserView.model_validate(first),
            "second-token": UserView.model_validate(second),
        },
        {
            "first_user": first.id,
            "second_user": second.id,
            "first_key": first_key.id,
            "revoked_key": revoked_key.id,
            "second_key": second_key.id,
        },
    )


def _window() -> dict[str, str]:
    return {
        "from": "2026-08-18T12:00:00Z",
        "to": "2026-08-18T14:00:00Z",
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_auth(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "secret"},
    )
    assert response.status_code == 200
    return _auth(response.json()["token"])


@contextmanager
def reporting_client(
    postgresql_url: str,
    postgresql: dict[str, object],
) -> Iterator[tuple[TestClient, dict[str, object]]]:
    users, ids = asyncio.run(_seed(postgresql_url))
    app = create_app(_config(postgresql))
    app.dependency_overrides[get_user_service] = lambda: ReportingUserService(users)
    with TestClient(app) as client:
        yield client, ids


def test_user_reporting_isolated_by_identity_and_key(
    postgresql_url: str,
    postgresql: dict[str, object],
) -> None:
    with reporting_client(postgresql_url, postgresql) as (client, ids):
        first = client.get(
            "/api/user/usage", params=_window(), headers=_auth("first-token")
        )
        second = client.get(
            "/api/user/usage", params=_window(), headers=_auth("second-token")
        )
        own_key = client.get(
            "/api/user/usage",
            params=_window() | {"api_key_ids": str(ids["revoked_key"])},
            headers=_auth("first-token"),
        )
        foreign_key = client.get(
            "/api/user/usage",
            params=_window() | {"api_key_ids": str(ids["second_key"])},
            headers=_auth("first-token"),
        )
    assert first.status_code == second.status_code == own_key.status_code == 200
    assert first.json()["requests"] == 2
    assert first.json()["total_tokens"] == 15
    assert first.json()["cost_usd"] == "0.100000000001"
    assert first.json()["metered_requests"] == 1
    assert first.json()["costed_requests"] == 1
    assert {row["model"] for row in first.json()["models"]} == {
        "alpha",
        "beta-deleted",
    }
    assert any(row["revoked"] for row in first.json()["api_keys"])
    assert second.json()["requests"] == 1
    assert second.json()["cost_usd"] == "0"
    assert own_key.json()["requests"] == 1
    assert own_key.json()["total_tokens"] is None
    assert foreign_key.status_code == 422
    assert "Unknown API key" in foreign_key.json()["detail"]


def test_user_series_gap_filling_and_range_validation(
    postgresql_url: str,
    postgresql: dict[str, object],
) -> None:
    with reporting_client(postgresql_url, postgresql) as (client, _):
        series = client.get(
            "/api/user/usage/series",
            params=_window() | {"bucket": "hour"},
            headers=_auth("first-token"),
        )
        too_many = client.get(
            "/api/user/usage/series",
            params={
                "from": "2026-08-01T00:00:00Z",
                "to": "2026-08-03T00:00:00Z",
                "bucket": "minute",
            },
            headers=_auth("first-token"),
        )
    assert series.status_code == 200
    assert [point["requests"] for point in series.json()["points"]] == [2, 0]
    assert series.json()["points"][1]["total_tokens"] is None
    assert series.json()["points"][1]["cost_usd"] is None
    assert too_many.status_code == 422


def test_admin_reporting_authorization_and_filters(
    postgresql_url: str,
    postgresql: dict[str, object],
) -> None:
    with reporting_client(postgresql_url, postgresql) as (client, ids):
        unauthenticated = client.get("/api/admin/usage", params=_window())
        user_authenticated = client.get(
            "/api/admin/usage", params=_window(), headers=_auth("first-token")
        )
        admin_headers = _admin_auth(client)
        all_users = client.get(
            "/api/admin/usage", params=_window(), headers=admin_headers
        )
        filtered = client.get(
            "/api/admin/usage",
            params=_window() | {"user_id": str(ids["first_user"]), "models": "alpha"},
            headers=admin_headers,
        )
        multi_model = client.get(
            "/api/admin/usage",
            params=list(_window().items())
            + [("models", "alpha"), ("models", "not-recorded")],
            headers=admin_headers,
        )
        empty = client.get(
            "/api/admin/usage",
            params=_window()
            | {
                "user_id": str(ids["first_user"]),
                "api_key_ids": str(ids["second_key"]),
            },
            headers=admin_headers,
        )
    assert unauthenticated.status_code == user_authenticated.status_code == 401
    assert all_users.status_code == 200
    assert all_users.json()["requests"] == 3
    assert len(all_users.json()["users"]) == 2
    assert filtered.json()["requests"] == 1
    assert filtered.json()["cost_usd"] == "0.100000000001"
    assert multi_model.json()["requests"] == 2
    assert empty.json()["requests"] == 0
    assert empty.json()["models"] == []
    assert empty.json()["api_keys"] == []
    assert empty.json()["users"] == []


async def test_high_cardinality_report_uses_composite_indexes(
    postgresql_url: str,
) -> None:
    _, ids = await _seed(postgresql_url)
    engine = create_engine(postgresql_url)
    factory = create_session_factory(engine)
    start = datetime(2026, 8, 1, tzinfo=UTC)
    end = datetime(2026, 8, 19, tzinfo=UTC)
    try:
        async with factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO model_usage_events (
                        user_id, api_key_id, model_name, provider, status_code,
                        input_tokens, output_tokens, total_tokens, cost_usd,
                        duration_ms, error_type, streaming, ts
                    )
                    SELECT
                        :user_id, :api_key_id, 'alpha', 'openai', 200,
                        10, 5, 15, 0.0001, 20, NULL, FALSE,
                        CAST(:start AS timestamptz) + (series || ' seconds')::interval
                    FROM generate_series(1, 20000) AS series
                    """
                ),
                {
                    "user_id": ids["first_user"],
                    "api_key_id": ids["first_key"],
                    "start": start,
                },
            )
            await session.commit()

        filters = ModelUsageFilters(
            start=start,
            end=end,
            user_id=ids["first_user"],
            api_key_ids=(ids["first_key"],),
            models=("alpha",),
        )
        began = time.perf_counter()
        totals = await ModelUsageRepository(factory).totals(filters)
        duration = time.perf_counter() - began

        plans: list[str] = []
        async with factory() as session:
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            for statement, value in (
                (
                    USER_EXPLAIN,
                    ids["first_user"],
                ),
                (
                    KEY_EXPLAIN,
                    ids["first_key"],
                ),
                (
                    MODEL_EXPLAIN,
                    "alpha",
                ),
            ):
                plan = (
                    await session.execute(
                        text(statement),
                        {"value": value, "start": start, "end": end},
                    )
                ).scalar_one()
                plans.append(json.dumps(plan))
    finally:
        await engine.dispose()

    assert totals.requests == 20_001
    assert duration < 2.0
    assert "ix_model_usage_events_user_ts" in plans[0]
    assert "ix_model_usage_events_api_key_ts" in plans[1]
    assert "ix_model_usage_events_model_ts" in plans[2]
