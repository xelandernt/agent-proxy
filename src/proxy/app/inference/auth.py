from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Request

from proxy.api_keys.schemas import AuthenticatedApiKey
from proxy.app.dependencies import ApiKeyServiceDep
from proxy.app.inference.errors import OpenAIErrorException

logger = logging.getLogger(__name__)


async def get_proxy_api_key(
    request: Request,
    service: ApiKeyServiceDep,
) -> AuthenticatedApiKey:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not value.strip():
        raise _invalid_key()
    key = await service.authenticate(value.strip())
    if key is None:
        raise _invalid_key()
    try:
        await service.mark_used(key.id)
    except Exception:
        logger.warning("Could not update API key last-used timestamp.", exc_info=True)
    return key


def _invalid_key() -> OpenAIErrorException:
    return OpenAIErrorException(
        401,
        "Invalid or missing API key.",
        error_type="authentication_error",
        code="invalid_api_key",
    )


ProxyApiKeyDep = Annotated[AuthenticatedApiKey, Depends(get_proxy_api_key)]
