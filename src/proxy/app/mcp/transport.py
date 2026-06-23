import json
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

import niquests
from fastapi import status
from starlette.types import ASGIApp

PROXY_ONLY_REQUEST_HEADERS = {
    "authorization",
    "host",
}


@dataclass(frozen=True)
class UpstreamResponseHandle:
    session: niquests.Session
    response: niquests.Response


def filter_request_headers(
    headers: Mapping[str, str],
    strip_headers: set[str],
) -> dict[str, str]:
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
    upstream_app: ASGIApp | None,
) -> UpstreamResponseHandle:
    target_url = build_target_url(url, query, use_asgi_app=upstream_app is not None)

    if upstream_app is not None:
        session = niquests.Session(
            app=upstream_app,
            base_url="asgi://default",
            timeout=(10.0, 3600.0),
        )
    else:
        session = niquests.Session(timeout=(10.0, 3600.0))

    try:
        response = session.request(
            method=method,
            url=target_url,
            data=body,
            headers=headers,
            allow_redirects=False,
            stream=upstream_app is None,
        )
    except niquests.exceptions.RequestException:
        session.close()
        raise

    return UpstreamResponseHandle(session=session, response=response)


def build_target_url(url: str, query: str, *, use_asgi_app: bool) -> str:
    parsed = urlsplit(url)
    merged_query = urlencode(
        parse_qsl(parsed.query, keep_blank_values=True), doseq=True
    )
    request_query = urlencode(parse_qsl(query, keep_blank_values=True), doseq=True)
    combined_query = "&".join(part for part in [merged_query, request_query] if part)

    if use_asgi_app:
        path = parsed.path or "/"
        return path if not combined_query else f"{path}?{combined_query}"

    rebuilt = SplitResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=parsed.path,
        query=combined_query,
        fragment=parsed.fragment,
    )
    return urlunsplit(rebuilt)


def read_response_payload(handle: UpstreamResponseHandle) -> bytes:
    try:
        return handle.response.content or b""
    finally:
        handle.response.close()
        handle.session.close()


def is_event_stream(response: niquests.Response) -> bool:
    content_type = response.headers.get("content-type", "")
    normalized_content_type = (
        content_type.decode() if isinstance(content_type, bytes) else str(content_type)
    )
    return normalized_content_type.startswith("text/event-stream")


def response_status_code(response: niquests.Response) -> int:
    return int(response.status_code or status.HTTP_502_BAD_GATEWAY)


def stream_upstream_response(
    handle: UpstreamResponseHandle,
) -> Generator[bytes, None, None]:
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
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    stripped_value = value.strip()
    return stripped_value or None
