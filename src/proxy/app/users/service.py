from __future__ import annotations

from proxy.app.users.auth import UserAuthProvider, UserIdentityError
from proxy.app.users.repository import UserRepository
from proxy.app.users.schemas import UserView


class UserAuthenticationError(ValueError):
    """Raised when a session token cannot identify a usable user."""


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        provider: UserAuthProvider,
    ) -> None:
        self._repository = repository
        self._provider = provider

    async def authenticate(self, token: str) -> UserView:
        try:
            principal = await self._provider.resolve_principal(token)
        except UserIdentityError as error:
            raise UserAuthenticationError(str(error)) from error
        if principal is None:
            raise UserAuthenticationError("Invalid or expired bearer token.")
        user = await self._repository.upsert(principal)
        return UserView.model_validate(user)

    async def login(self, username: str, password: str) -> tuple[str, UserView]:
        token = await self._provider.login(username, password)
        if token is None:
            raise UserAuthenticationError("Invalid username or password.")
        return token, await self.authenticate(token)
