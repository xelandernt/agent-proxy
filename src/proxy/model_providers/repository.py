from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.model_deployments.models import ModelDeploymentRecord
from proxy.model_providers.models import ModelProviderRecord


class ModelProviderNotFound(KeyError):
    pass


class ModelProviderNameTaken(ValueError):
    pass


class ModelProviderInUse(ValueError):
    def __init__(self, name: str, models: list[str]) -> None:
        self.name = name
        self.models = tuple(sorted(models))
        super().__init__(
            f"Model provider '{name}' is used by models: {', '.join(self.models)}."
        )


class ModelProviderRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_all(self) -> list[ModelProviderRecord]:
        async with self._session_factory() as session:
            return list(
                (
                    await session.execute(
                        select(ModelProviderRecord).order_by(ModelProviderRecord.name)
                    )
                )
                .scalars()
                .all()
            )

    async def get(self, name: str) -> ModelProviderRecord | None:
        async with self._session_factory() as session:
            return await session.get(ModelProviderRecord, name)

    async def create(
        self,
        *,
        name: str,
        config: dict[str, object],
        encrypted_credentials: str,
        credential_names: list[str],
    ) -> ModelProviderRecord:
        now = datetime.now(UTC)
        row = ModelProviderRecord(
            name=name,
            config=config,
            encrypted_credentials=encrypted_credentials,
            credential_names=credential_names,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ModelProviderNameTaken(
                    f"Model provider name '{name}' already exists."
                ) from error
            await session.refresh(row)
        return row

    async def update(
        self,
        name: str,
        *,
        config: dict[str, object],
        encrypted_credentials: str,
        credential_names: list[str],
    ) -> ModelProviderRecord:
        async with self._session_factory() as session:
            row = await session.get(ModelProviderRecord, name)
            if row is None:
                raise ModelProviderNotFound(f"Unknown model provider '{name}'.")
            row.config = config
            row.encrypted_credentials = encrypted_credentials
            row.credential_names = credential_names
            row.updated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(row)
        return row

    async def delete(self, name: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(ModelProviderRecord, name)
            if row is None:
                raise ModelProviderNotFound(f"Unknown model provider '{name}'.")
            models = list(
                (
                    await session.execute(
                        select(ModelDeploymentRecord.name)
                        .where(ModelDeploymentRecord.provider == name)
                        .order_by(ModelDeploymentRecord.name)
                    )
                )
                .scalars()
                .all()
            )
            if models:
                raise ModelProviderInUse(name, models)
            await session.execute(
                delete(ModelProviderRecord).where(ModelProviderRecord.name == name)
            )
            await session.commit()
