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

"""Shared HTTP test infrastructure for MCP protocol and transport tests.

Provides the mcp_session fixture (initialized TestClient + session headers),
call_tool helper (builds JSON-RPC tools/call requests), and parse_tool_result
helper (extracts tool results from SSE responses).
"""

import json

import pytest
from starlette.testclient import TestClient

from src.http_transport import _json_rpc_404_handler
from src.mcp_app import mcp

import src.tools_extract  # noqa: F401 -- trigger tool registration
import src.tools_write  # noqa: F401

INIT_BODY = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
}

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _fresh_app():
    """Build a Starlette app with a fresh session manager and 404 handler."""
    mcp._session_manager = None
    app = mcp.streamable_http_app()
    app.exception_handlers[404] = _json_rpc_404_handler
    return app


@pytest.fixture(autouse=True)
def _reset_session_manager():
    """Reset session manager after every test so the next one gets a fresh one."""
    yield
    mcp._session_manager = None


@pytest.fixture()
def mcp_session():
    """TestClient with lifespan, correct Host, and completed init handshake.

    Yields (client, session_headers) where session_headers includes
    Content-Type, Accept, and Mcp-Session-Id for subsequent requests.
    """
    app = _fresh_app()
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Host": "localhost:8000"},
    ) as client:
        resp = client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
        assert resp.status_code == 200
        session_id = resp.headers.get("mcp-session-id")

        # Send initialized notification to complete handshake
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        notif_headers = {**MCP_HEADERS, "Mcp-Session-Id": session_id}
        client.post("/mcp", json=notif, headers=notif_headers)

        session_headers = {**MCP_HEADERS, "Mcp-Session-Id": session_id}
        yield client, session_headers


def call_tool(client, headers, tool_name, arguments, request_id=99):
    """Send a JSON-RPC tools/call request and return the raw response."""
    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": request_id,
        "params": {"name": tool_name, "arguments": arguments},
    }
    return client.post("/mcp", json=body, headers=headers)


def parse_tool_result(response) -> dict:
    """Extract the tool result dict from an SSE response.

    Parses the SSE text, finds the data line containing a JSON-RPC result,
    extracts result.content[0].text, and parses that as JSON.

    Raises ValueError if no result is found in the response.
    """
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            msg = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if "result" not in msg:
            continue
        content = msg["result"].get("content", [])
        if not content:
            continue
        text = content[0].get("text", "")
        return json.loads(text)

    raise ValueError(
        f"No tool result found in SSE response: {response.text[:500]}"
    )
