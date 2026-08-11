from __future__ import annotations

import json
from pathlib import Path

import pytest

from proxy.cli.cli import cli


def test_openapi_dumps_schema(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    with pytest.raises(SystemExit) as exc_info:
        cli(["openapi", str(output)])
    assert exc_info.value.code == 0
    schema = json.loads(output.read_text())
    assert schema["openapi"].startswith("3.")
    assert "/.well-known/mcp-servers" in schema["paths"]
    assert "/api/servers/{name}/usage" in schema["paths"]
    assert "/api/admin/servers" in schema["paths"]
