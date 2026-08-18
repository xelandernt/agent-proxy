from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from proxy.app.users.models import UserRecord
from proxy.app.users.schemas import UserPrincipal


class UserRepository:
    """Persistence for verified interactive users."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def upsert(self, principal: UserPrincipal) -> UserRecord:
        now = datetime.now(UTC)
        statement = (
            insert(UserRecord)
            .values(
                issuer=principal.issuer,
                subject=principal.subject,
                email=principal.email,
                email_verified=principal.email_verified,
                display_name=principal.display_name,
                created_at=now,
                last_login_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_users_issuer_subject",
                set_={
                    "email": principal.email,
                    "email_verified": principal.email_verified,
                    "display_name": principal.display_name,
                    "last_login_at": now,
                },
            )
            .returning(UserRecord)
        )
        async with self._session_factory() as session:
            user = (await session.execute(statement)).scalar_one()
            await session.commit()
            return user
