from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from proxy.model_deployments.schemas import ModelPricingView


class UserPrincipal(BaseModel):
    """Verified identity claims used to resolve a durable user."""

    model_config = ConfigDict(extra="forbid")

    issuer: str
    subject: str
    email: str
    email_verified: bool | None = None
    display_name: str | None = None


class UserView(BaseModel):
    """Current account identity returned to the browser."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    email_verified: bool | None
    display_name: str | None
    created_at: datetime
    last_login_at: datetime


class AvailableModelView(BaseModel):
    """Public model metadata available for API-key scope selection."""

    name: str
    pricing: ModelPricingView | None


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionRequest(BaseModel):
    token: str


class LoginResponse(BaseModel):
    token: str
    user: UserView


class SessionResponse(BaseModel):
    authenticated: bool
    user: UserView


class OAuthBrowserInfo(BaseModel):
    issuer: str
    client_id: str
    scopes: list[str]


class UserAuthStatus(BaseModel):
    provider: str
    oauth: OAuthBrowserInfo | None
