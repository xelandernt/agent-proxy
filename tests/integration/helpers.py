import json
import socket


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def parse_sse_data(text: str) -> list[dict]:
    results = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            results.append(json.loads(line[6:]))
    return results
