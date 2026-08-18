from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from proxy.app.dependencies import CurrentUserDep, UserServiceDep
from proxy.app.users.auth import (
    clear_user_session_cookie,
    get_user_provider,
    set_user_session_cookie,
    user_cookie_policy,
    user_request_is_secure,
)
from proxy.app.users.schemas import (
    LoginRequest,
    LoginResponse,
    OAuthBrowserInfo,
    SessionRequest,
    SessionResponse,
    UserAuthStatus,
    UserView,
)
from proxy.app.users.service import UserAuthenticationError

public_router = APIRouter(prefix="/api/user", tags=["user"])
router = APIRouter(prefix="/api/user", tags=["user"])


@public_router.get("/auth-status", response_model=UserAuthStatus)
def auth_status(request: Request) -> UserAuthStatus:
    provider = get_user_provider(request)
    config = request.app.state.config.user
    flow = provider.oauth_browser_flow()
    return UserAuthStatus(
        provider=config.auth.provider,
        oauth=(
            OAuthBrowserInfo(
                issuer=flow.issuer,
                client_id=flow.client_id,
                scopes=config.oauth_scopes,
            )
            if flow is not None
            else None
        ),
    )


@public_router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: UserServiceDep,
) -> LoginResponse:
    try:
        token, user = await service.login(payload.username, payload.password)
    except UserAuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    set_user_session_cookie(
        response,
        token,
        secure=user_request_is_secure(request),
        samesite=user_cookie_policy(request),
    )
    return LoginResponse(token=token, user=user)


@public_router.post("/session", response_model=SessionResponse)
async def establish_session(
    payload: SessionRequest,
    request: Request,
    response: Response,
    service: UserServiceDep,
) -> SessionResponse:
    try:
        user = await service.authenticate(payload.token)
    except UserAuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    set_user_session_cookie(
        response,
        payload.token,
        secure=user_request_is_secure(request),
        samesite=user_cookie_policy(request),
    )
    return SessionResponse(authenticated=True, user=user)


@public_router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(response: Response) -> None:
    clear_user_session_cookie(response)


@router.get("/me", response_model=UserView)
async def me(user: CurrentUserDep) -> UserView:
    return user
