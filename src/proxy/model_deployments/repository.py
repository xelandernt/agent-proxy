from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.model_deployments.models import ModelDeploymentRecord


class ModelDeploymentNotFound(KeyError):
    pass


class ModelDeploymentNameTaken(ValueError):
    pass


class ModelDeploymentReferenced(ValueError):
    pass


class ModelDeploymentProviderNotFound(ValueError):
    pass


class ModelDeploymentRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_all(self) -> list[ModelDeploymentRecord]:
        async with self._session_factory() as session:
            return list(
                (
                    await session.execute(
                        select(ModelDeploymentRecord).order_by(
                            ModelDeploymentRecord.name
                        )
                    )
                )
                .scalars()
                .all()
            )

    async def get(self, name: str) -> ModelDeploymentRecord | None:
        async with self._session_factory() as session:
            return await session.get(ModelDeploymentRecord, name)

    async def create(
        self, *, name: str, provider: str, model_id: str
    ) -> ModelDeploymentRecord:
        now = datetime.now(UTC)
        row = ModelDeploymentRecord(
            name=name,
            provider=provider,
            model_id=model_id,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if await session.get(ModelDeploymentRecord, name) is not None:
                    raise ModelDeploymentNameTaken(
                        f"Model name '{name}' already exists."
                    ) from error
                raise ModelDeploymentProviderNotFound(
                    f"Unknown model provider '{provider}'."
                ) from error
            await session.refresh(row)
        return row

    async def update(
        self, name: str, *, provider: str, model_id: str
    ) -> ModelDeploymentRecord:
        async with self._session_factory() as session:
            row = await session.get(ModelDeploymentRecord, name)
            if row is None:
                raise ModelDeploymentNotFound(f"Unknown model '{name}'.")
            row.provider = provider
            row.model_id = model_id
            row.updated_at = datetime.now(UTC)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ModelDeploymentProviderNotFound(
                    f"Unknown model provider '{provider}'."
                ) from error
            await session.refresh(row)
        return row

    async def delete(self, name: str) -> None:
        async with self._session_factory() as session:
            try:
                result = await session.execute(
                    delete(ModelDeploymentRecord).where(
                        ModelDeploymentRecord.name == name
                    )
                )
                if result.rowcount == 0:
                    raise ModelDeploymentNotFound(f"Unknown model '{name}'.")
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ModelDeploymentReferenced(
                    f"Model '{name}' is selected by an active API key."
                ) from error
