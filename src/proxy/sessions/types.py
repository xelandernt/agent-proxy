from dataclasses import dataclass


@dataclass(frozen=True)
class SessionOwner:
    issuer: str
    subject: str


class SessionOwnershipConflictError(Exception):
    pass
