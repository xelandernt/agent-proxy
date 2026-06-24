import json
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

import niquests
from fastapi import status

PROXY_ONLY_REQUEST_HEADERS = {
    "authorization",
    "host",
}


@dataclass(frozen=True)
class UpstreamResponseHandle:
    """Handle holding the upstream HTTP session and response.

    Attributes:
        session: The niquests session used for the upstream request.
        response: The upstream HTTP response.
    """

    session: niquests.Session
    response: niquests.Response


def filter_request_headers(
    headers: Mapping[str, str],
    strip_headers: set[str],
) -> dict[str, str]:
    """Remove proxy-only and configured headers from an incoming request.

    Strips headers like ``authorization`` and ``host`` that should not be
    forwarded, along with any additional headers in ``strip_headers``.

    Args:
        headers: The incoming request headers.
        strip_headers: Set of header names (lowercase) to strip.

    Returns:
        Filtered headers dictionary safe for forwarding.
    """
    filtered: dict[str, str] = {}
    for header_name, header_value in headers.items():
        normalized_name = header_name.lower()
        if normalized_name in strip_headers:
            continue
        if normalized_name in PROXY_ONLY_REQUEST_HEADERS:
            continue
        filtered[header_name] = header_value
    return filtered


def filter_response_headers(
    headers: Mapping[str, str],
    strip_headers: set[str],
) -> dict[str, str]:
    """Remove configured headers from an upstream response.

    Strips any headers whose lowercase name appears in ``strip_headers``.

    Args:
        headers: The upstream response headers.
        strip_headers: Set of header names (lowercase) to strip.

    Returns:
        Filtered headers dictionary safe for returning to the client.
    """
    filtered: dict[str, str] = {}
    for header_name, header_value in headers.items():
        normalized_name = header_name.lower()
        if normalized_name in strip_headers:
            continue
        filtered[header_name] = header_value
    return filtered


def send_upstream_request(
    *,
    url: str,
    method: str,
    body: bytes,
    headers: dict[str, str],
    query: str,
) -> UpstreamResponseHandle:
    """Send an HTTP request to the upstream MCP server.

    Constructs the target URL by merging the server URL with the incoming
    query string, then creates a new niquests session and sends the request
    with streaming enabled.

    Args:
        url: The upstream server base URL.
        method: HTTP method for the request.
        body: Raw request body bytes.
        headers: Request headers to forward.
        query: Raw query string to append.

    Returns:
        An UpstreamResponseHandle with the session and response.

    Raises:
        niquests.exceptions.RequestException: If the upstream request fails.
    """
    target_url = build_target_url(url, query)
    session = niquests.Session(timeout=(10.0, 3600.0))

    try:
        response = session.request(
            method=method,
            url=target_url,
            data=body,
            headers=headers,
            allow_redirects=False,
            stream=True,
        )
    except niquests.exceptions.RequestException:
        session.close()
        raise

    return UpstreamResponseHandle(session=session, response=response)


def build_target_url(url: str, query: str) -> str:
    """Merge an upstream URL with an incoming request query string.

    If the upstream URL already has query parameters they are preserved and
    combined with the incoming query string.

    Args:
        url: The upstream server URL.
        query: The raw query string from the incoming request.

    Returns:
        The fully constructed target URL.
    """
    parsed = urlsplit(url)
    merged_query = urlencode(
        parse_qsl(parsed.query, keep_blank_values=True), doseq=True
    )
    request_query = urlencode(parse_qsl(query, keep_blank_values=True), doseq=True)
    combined_query = "&".join(part for part in [merged_query, request_query] if part)

    rebuilt = SplitResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=parsed.path,
        query=combined_query,
        fragment=parsed.fragment,
    )
    return urlunsplit(rebuilt)


def read_response_payload(handle: UpstreamResponseHandle) -> bytes:
    """Read the full response payload and close the upstream connection.

    Args:
        handle: The upstream response handle to consume.

    Returns:
        The complete response body as bytes.
    """
    try:
        return handle.response.content or b""
    finally:
        handle.response.close()
        handle.session.close()


def is_event_stream(response: niquests.Response) -> bool:
    """Check whether the upstream response is a server-sent event stream.

    Args:
        response: The upstream HTTP response.

    Returns:
        True if the content type starts with ``text/event-stream``.
    """
    content_type = response.headers.get("content-type", "")
    normalized_content_type = (
        content_type.decode() if isinstance(content_type, bytes) else str(content_type)
    )
    return normalized_content_type.startswith("text/event-stream")


def response_status_code(response: niquests.Response) -> int:
    """Get the HTTP status code from an upstream response.

    Falls back to 502 Bad Gateway if the response has no status code.

    Args:
        response: The upstream HTTP response.

    Returns:
        The integer HTTP status code.
    """
    return int(response.status_code or status.HTTP_502_BAD_GATEWAY)


def stream_upstream_response(
    handle: UpstreamResponseHandle,
) -> Generator[bytes, None, None]:
    """Stream the upstream response body in chunks.

    Reads the response in 64 KiB chunks and yields each chunk as bytes.
    The upstream connection is closed when the stream is exhausted.

    Args:
        handle: The upstream response handle to stream from.

    Yields:
        Bytes chunks from the upstream response body.
    """
    try:
        for chunk in handle.response.iter_content(chunk_size=64 * 1024):
            if isinstance(chunk, str):
                yield chunk.encode()
            elif chunk:
                yield chunk
    finally:
        handle.response.close()
        handle.session.close()


def extract_jsonrpc_method(method: str, body: bytes) -> str | None:
    """Extract the JSON-RPC method name from a request body.

    Only meaningful for POST requests with a JSON body that is a JSON-RPC
    call object containing a ``method`` field.

    Args:
        method: The HTTP method of the request.
        body: The raw request body bytes.

    Returns:
        The JSON-RPC method name, or None if it cannot be extracted.
    """
    if method != "POST" or not body:
        return None

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    candidate = payload.get("method")
    return candidate if isinstance(candidate, str) else None


def optional_header_value(value: str | bytes | None) -> str | None:
    """Normalize an optional header value to ``str | None``.

    Converts bytes to str and treats empty or whitespace-only strings as
    None.

    Args:
        value: The raw header value, which may be None, str, or bytes.

    Returns:
        The stripped string value, or None.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    stripped_value = value.strip()
    return stripped_value or None
