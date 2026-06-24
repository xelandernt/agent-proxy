from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy ORM models."""


class SessionBinding(Base):
    """SQLAlchemy model for MCP session ownership bindings.

    Tracks which principal (issuer + subject) owns each session, along
    with the optional OAuth client ID that created the binding.

    Attributes:
        server_name: The MCP server name (part of composite PK).
        session_id: The session ID (part of composite PK).
        issuer: The OIDC issuer of the owning principal.
        subject: The subject identifier of the owning principal.
        client_id: Optional OAuth client ID that bound the session.
    """

    __tablename__ = "mcp_session_bindings"

    server_name: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    issuer: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
