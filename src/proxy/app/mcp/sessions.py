from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class SessionOwner:
    issuer: str
    subject: str
    client_id: str | None


class SessionRegistry:
    def __init__(self) -> None:
        self._bindings: dict[tuple[str, str], SessionOwner] = {}
        self._lock = Lock()

    def bind(self, *, server_name: str, session_id: str, owner: SessionOwner) -> None:
        with self._lock:
            self._bindings[(server_name, session_id)] = owner

    def get(self, *, server_name: str, session_id: str) -> SessionOwner | None:
        with self._lock:
            return self._bindings.get((server_name, session_id))

    def remove(self, *, server_name: str, session_id: str) -> None:
        with self._lock:
            self._bindings.pop((server_name, session_id), None)
