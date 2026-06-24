from dataclasses import dataclass


@dataclass(frozen=True)
class SessionOwner:
    """Identity of a principal that owns an MCP session.

    Attributes:
        issuer: The OIDC issuer URL of the principal.
        subject: The subject identifier of the principal.
    """

    issuer: str
    subject: str


class SessionOwnershipConflictError(Exception):
    """Raised when a request attempts to use a session bound to another principal."""
