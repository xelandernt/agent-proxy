from __future__ import annotations

import pytest

import proxy.app.main as main_module


class StubEngine:
    """Stand-in AsyncEngine whose connections never touch a real database."""

    def begin(self) -> StubConnectionContext:
        return StubConnectionContext()

    async def dispose(self) -> None:
        return None


class StubConnectionContext:
    async def __aenter__(self) -> StubConnection:
        return StubConnection()

    async def __aexit__(self, *_args: object) -> None:
        return None


class StubConnection:
    async def run_sync(self, _function: object) -> None:
        return None


class StubServerManager:
    """Stand-in manager that boots an empty server inventory."""

    def __init__(self, **_kwargs: object) -> None:
        return None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


@pytest.fixture(autouse=True)
def without_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests off the database: stub the engine and server manager."""
    monkeypatch.setattr(main_module, "create_engine", lambda _url: StubEngine())
    monkeypatch.setattr(main_module, "ServerManager", StubServerManager)
