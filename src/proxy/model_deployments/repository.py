from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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


class ModelDeploymentRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def list_all(self) -> list[ModelDeploymentRecord]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(ModelDeploymentRecord).order_by(ModelDeploymentRecord.name)
                )
            ).scalars()
            return list(rows.all())

    async def get(self, name: str) -> ModelDeploymentRecord | None:
        async with self._session_factory() as session:
            return (
                await session.execute(
                    select(ModelDeploymentRecord).where(
                        ModelDeploymentRecord.name == name
                    )
                )
            ).scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        description: str,
        upstream_model: str,
        api_base: str | None,
        settings: dict[str, Any],
        encrypted_secrets: str,
        secret_names: list[str],
    ) -> ModelDeploymentRecord:
        now = datetime.now(UTC)
        row = ModelDeploymentRecord(
            name=name,
            description=description,
            upstream_model=upstream_model,
            api_base=api_base,
            settings=settings,
            encrypted_secrets=encrypted_secrets,
            secret_names=secret_names,
            created_at=now,
            updated_at=now,
        )
        async with self._session_factory() as session:
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise ModelDeploymentNameTaken(
                    f"Model name '{name}' already exists."
                ) from error
            await session.refresh(row)
            return row

    async def update(
        self,
        name: str,
        *,
        description: str,
        upstream_model: str,
        api_base: str | None,
        settings: dict[str, Any],
        encrypted_secrets: str,
        secret_names: list[str],
    ) -> ModelDeploymentRecord:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(ModelDeploymentRecord).where(
                        ModelDeploymentRecord.name == name
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise ModelDeploymentNotFound(f"Unknown model '{name}'.")
            row.description = description
            row.upstream_model = upstream_model
            row.api_base = api_base
            row.settings = settings
            row.encrypted_secrets = encrypted_secrets
            row.secret_names = secret_names
            row.updated_at = datetime.now(UTC)
            await session.commit()
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
