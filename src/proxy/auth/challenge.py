from collections.abc import Iterable

AUTHORIZATION_HEADER = "Authorization"


def build_auth_challenge(
    *,
    resource_metadata_url: str,
    scopes: Iterable[str],
    error: str | None = None,
    error_description: str | None = None,
) -> str:
    """Build a ``WWW-Authenticate`` header value for Bearer challenges.

    Constructs a challenge string in the format defined by RFC 6750 and
    RFC 8414, including the resource metadata URL and scopes.

    Args:
        resource_metadata_url: URL to the OAuth protected resource metadata
            for the MCP server being accessed.
        scopes: Iterable of scope strings to include in the challenge.
        error: Optional error code (e.g. ``insufficient_scope``).
        error_description: Optional human-readable error description.

    Returns:
        A ``WWW-Authenticate`` header value string.
    """
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
