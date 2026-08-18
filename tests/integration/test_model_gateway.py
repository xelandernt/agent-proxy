from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select
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
from proxy.security.credentials import CredentialCipher

DEVELOPMENT_FERNET_KEY = "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="


@pytest.fixture()
async def session_factory(
    postgresql_url: str,
) -> AsyncIterator[async_sessionmaker]:
    engine: AsyncEngine = create_engine(postgresql_url)
    await create_all_tables(engine)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


async def test_user_model_key_and_usage_lifecycle(
    session_factory: async_sessionmaker,
) -> None:
    users = UserRepository(session_factory)
    models = ModelDeploymentService(
        ModelDeploymentRepository(session_factory),
        CredentialCipher(SecretStr(DEVELOPMENT_FERNET_KEY)),
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

    await models.create(
        ModelDeploymentCreate(
            name="claude",
            description="Primary model",
            upstream_model="anthropic/claude-sonnet-4-5",
            settings={"timeout": 120},
            secrets={"api_key": "provider-secret-value"},
        )
    )
    await models.create(
        ModelDeploymentCreate(
            name="azure",
            upstream_model="azure/gpt-5",
            api_base="https://example.openai.azure.com",
            secrets={"api_key": "azure-secret-value"},
        )
    )

    async with session_factory() as session:
        stored = await session.get(ModelDeploymentRecord, "claude")
        assert stored is not None
        assert "provider-secret-value" not in stored.encrypted_secrets
        assert stored.secret_names == ["api_key"]

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
        assert not (
            {"input", "output", "instructions"} & set(event.__table__.columns.keys())
        )

    await keys.revoke(created.id, user.id)
    assert await keys.authenticate(created.key) is None
    await models.delete("azure")
