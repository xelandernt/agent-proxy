from collections.abc import Iterable

AUTHORIZATION_HEADER = "Authorization"


def build_auth_challenge(
    *,
    resource_metadata_url: str,
    scopes: Iterable[str],
    error: str | None = None,
    error_description: str | None = None,
) -> str:
    parts = [
        'Bearer realm="agent-proxy"',
        f'resource_metadata="{resource_metadata_url}"',
    ]
    challenge_scope = " ".join(sorted(set(scopes)))
    if challenge_scope:
        parts.append(f'scope="{challenge_scope}"')
    if error is not None:
        parts.append(f'error="{error}"')
    if error_description is not None:
        parts.append(f'error_description="{error_description}"')
    return ", ".join(parts)
