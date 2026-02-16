# Copyright (C) 2025 the contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Deeper HTTP error scenario tests beyond Phase 2 protocol tests (TEST-04).

Tests malformed JSON, missing required fields, invalid tool names, and
missing required tool arguments. Uses _fresh_app() for raw HTTP tests
that don't require a session, and mcp_session for session-based tests.
"""

import json

from starlette.testclient import TestClient

from tests.conftest import (
    MCP_HEADERS,
    _fresh_app,
    call_tool,
)


def test_malformed_json_returns_400():
    """POST /mcp with malformed JSON body returns 400 with parse error."""
    app = _fresh_app()
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Host": "localhost:8000"},
    ) as client:
        resp = client.post("/mcp", content=b"{broken", headers=MCP_HEADERS)
        assert resp.status_code == 400
        data = resp.json()
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == -32700


def test_missing_jsonrpc_field_returns_400():
    """POST /mcp without 'jsonrpc' field returns 400 with validation error."""
    app = _fresh_app()
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Host": "localhost:8000"},
    ) as client:
        body = {"method": "initialize", "id": 1}
        resp = client.post("/mcp", json=body, headers=MCP_HEADERS)
        assert resp.status_code == 400
        data = resp.json()
        assert data["jsonrpc"] == "2.0"
        assert "error" in data


def test_invalid_tool_name_returns_error(mcp_session):
    """Calling a nonexistent tool returns 200 with isError=true in result."""
    client, headers = mcp_session

    resp = call_tool(client, headers, "nonexistent_tool", {})
    assert resp.status_code == 200

    # Parse SSE to find the error result
    for line in resp.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        msg = json.loads(payload)
        if "result" not in msg:
            continue
        result = msg["result"]
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "unknown tool" in text.lower()
        return

    raise AssertionError("No error result found in SSE response")


def test_tool_with_missing_required_args(mcp_session):
    """Calling extract_structure_compact with no args returns isError=true."""
    client, headers = mcp_session

    resp = call_tool(client, headers, "extract_structure_compact", {})
    assert resp.status_code == 200

    # Parse SSE to find the error result
    for line in resp.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        msg = json.loads(payload)
        if "result" not in msg:
            continue
        result = msg["result"]
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "error" in text.lower()
        return

    raise AssertionError("No error result found in SSE response")
