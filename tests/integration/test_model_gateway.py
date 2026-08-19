from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from proxy.api_keys.repository import ApiKeyRepository
from proxy.api_keys.schemas import ApiKeyCreate, ApiKeyUpdate
from proxy.api_keys.service import ApiKeyService
from proxy.app.model_usage.models import ModelUsageEvent
from proxy.app.model_usage.recorder import ModelUsageRecord, ModelUsageRecorder
from proxy.app.users.repository import UserRepository
from proxy.app.users.schemas import UserPrincipal
from proxy.database import create_all_tables, create_engine, create_session_factory
from proxy.model_deployments.models import ModelDeploymentRecord
from proxy.model_deployments.repository import (
    ModelDeploymentReferenced,
    ModelDeploymentRepository,
)
from proxy.model_deployments.schemas import ModelDeploymentCreate
from proxy.model_deployments.service import ModelDeploymentService
from proxy.model_providers.repository import ModelProviderRepository
from proxy.model_providers.schemas import ModelProviderCreate
from proxy.model_providers.service import ModelProviderService
from proxy.security.credentials import CredentialCipher

DEVELOPMENT_FERNET_KEY = "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="


@pytest.fixture()
async def session_factory(
    postgresql_url: str,
) -> AsyncIterator[async_sessionmaker]:
    engine: AsyncEngine = create_engine(postgresql_url)
    await create_all_tables(engine)
    await create_all_tables(engine)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def test_fresh_schema_contains_cost_and_reporting_indexes(
    postgresql_url: str,
) -> None:
    engine = create_engine(postgresql_url)
    await create_all_tables(engine)
    try:
        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_columns(
                    "model_usage_events"
                )
            )
            indexes = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_indexes(
                    "model_usage_events"
                )
            )
    finally:
        await engine.dispose()

    cost = next(column for column in columns if column["name"] == "cost_usd")
    assert cost["nullable"] is True
    assert str(cost["type"]) == "NUMERIC(20, 12)"
    assert {
        ("user_id", "ts"),
        ("api_key_id", "ts"),
        ("model_name", "ts"),
    } <= {tuple(index["column_names"]) for index in indexes}


async def test_user_model_key_and_usage_lifecycle(
    session_factory: async_sessionmaker,
) -> None:
    users = UserRepository(session_factory)
    cipher = CredentialCipher(SecretStr(DEVELOPMENT_FERNET_KEY))
    providers = ModelProviderService(ModelProviderRepository(session_factory), cipher)
    models = ModelDeploymentService(
        ModelDeploymentRepository(session_factory), providers
    )
    keys = ApiKeyService(ApiKeyRepository(session_factory))

    user = await users.upsert(
        UserPrincipal(
            issuer="https://identity.example/realms/agents",
            subject="subject-1",
            email="first@example.com",
            email_verified=True,
            display_name="First User",
        )
    )
    updated = await users.upsert(
        UserPrincipal(
            issuer="https://identity.example/realms/agents",
            subject="subject-1",
            email="renamed@example.com",
            email_verified=True,
            display_name="Renamed User",
        )
    )
    assert updated.id == user.id
    assert updated.email == "renamed@example.com"

    await providers.create(
        ModelProviderCreate(
            name="anthropic-production",
            config={"provider": "anthropic", "api_key": "provider-secret-value"},
        )
    )
    await providers.create(
        ModelProviderCreate(
            name="azure-production",
            config={
                "provider": "azure_openai",
                "endpoint": "https://example.openai.azure.com",
                "api_version": "2026-06-01",
                "api_key": "azure-secret-value",
            },
        )
    )
    await models.create(
        ModelDeploymentCreate(
            name="claude",
            provider="anthropic-production",
            model_id="claude-sonnet-4-5",
        )
    )
    await models.create(
        ModelDeploymentCreate(
            name="azure",
            provider="azure-production",
            model_id="gpt-5",
        )
    )

    async with session_factory() as session:
        stored = await session.get(ModelDeploymentRecord, "claude")
        assert stored is not None
        assert stored.provider == "anthropic-production"
        assert stored.model_id == "claude-sonnet-4-5"

    created = await keys.create(
        user.id,
        ApiKeyCreate(name="Development", models=["claude"]),
    )
    authenticated = await keys.authenticate(created.key)
    assert authenticated is not None
    assert authenticated.user_id == user.id
    assert authenticated.models == frozenset({"claude"})

    await keys.update(
        created.id,
        user.id,
        ApiKeyUpdate(models=["azure"]),
    )
    authenticated = await keys.authenticate(created.key)
    assert authenticated is not None
    assert authenticated.models == frozenset({"azure"})

    await models.delete("claude")
    with pytest.raises(ModelDeploymentReferenced):
        await models.delete("azure")

    recorder = ModelUsageRecorder(session_factory)
    await recorder.start()
    recorder.record(
        ModelUsageRecord(
            user_id=user.id,
            api_key_id=created.id,
            model_name="azure",
            provider="azure",
            status_code=200,
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
            cached_tokens=6,
            cost_usd=Decimal("0.00042"),
            duration_ms=25,
            error_type=None,
            streaming=False,
            ts=datetime.now(UTC),
        )
    )
    await recorder.stop()

    async with session_factory() as session:
        event = (await session.execute(select(ModelUsageEvent))).scalar_one()
        assert event.model_name == "azure"
        assert event.total_tokens == 14
        assert event.cached_tokens == 6
        assert event.cost_usd == Decimal("0.000420000000")
        assert not (
            {"input", "output", "instructions"} & set(event.__table__.columns.keys())
        )

    await keys.revoke(created.id, user.id)
    assert await keys.authenticate(created.key) is None
    await models.delete("azure")
