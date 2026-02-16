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

"""Protocol compliance tests for TRANS-03/04/05/06.

Verifies JSON-RPC 2.0 requests, protocol version validation, Origin
validation (DNS rebinding), and error response format via TestClient.
Session manager is reset between tests (single-use ``run()`` limitation).
"""

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
def mcp_client():
    """TestClient with lifespan, correct Host, and completed init handshake."""
    app = _fresh_app()
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Host": "localhost:8000"},
    ) as client:
        resp = client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
        assert resp.status_code == 200
        session_id = resp.headers.get("mcp-session-id")
        client._session_id = session_id  # stash for tests
        yield client


# -- TRANS-03: JSON-RPC 2.0 POST requests ---------------------

def test_initialize_returns_200(mcp_client):
    """POST /mcp with valid JSON-RPC initialize body returns 200."""
    resp = mcp_client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 200

def test_tools_list_returns_tools(mcp_client):
    """POST /mcp with tools/list returns the registered MCP tools."""
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2,
        "params": {},
    }
    headers = {
        **MCP_HEADERS,
        "Mcp-Session-Id": mcp_client._session_id,
    }
    resp = mcp_client.post("/mcp", json=body, headers=headers)
    assert resp.status_code == 200

# -- TRANS-04: Protocol version validation ----------------------

def test_bad_protocol_version_returns_400(mcp_client):
    """POST /mcp with invalid mcp-protocol-version returns 400."""
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 3,
        "params": {},
    }
    headers = {
        **MCP_HEADERS,
        "Mcp-Session-Id": mcp_client._session_id,
        "mcp-protocol-version": "9999-99-99",
    }
    resp = mcp_client.post("/mcp", json=body, headers=headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert "supported" in data["error"]["message"].lower()

def test_missing_protocol_version_accepted(mcp_client):
    """POST /mcp without protocol version header succeeds (SDK defaults)."""
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 4,
        "params": {},
    }
    headers = {
        **MCP_HEADERS,
        "Mcp-Session-Id": mcp_client._session_id,
    }
    resp = mcp_client.post("/mcp", json=body, headers=headers)
    assert resp.status_code == 200

# -- TRANS-05: Origin validation (DNS rebinding) ----------------

def test_invalid_origin_returns_403():
    """POST /mcp with Origin: http://evil.com returns 403."""
    app = _fresh_app()
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Host": "localhost:8000"},
    ) as client:
        headers = {**MCP_HEADERS, "Origin": "http://evil.com"}
        resp = client.post("/mcp", json=INIT_BODY, headers=headers)
        assert resp.status_code == 403

def test_valid_origin_accepted(mcp_client):
    """POST /mcp with Origin: http://localhost:8000 returns 200."""
    headers = {**MCP_HEADERS, "Origin": "http://localhost:8000"}
    resp = mcp_client.post("/mcp", json=INIT_BODY, headers=headers)
    assert resp.status_code == 200

def test_missing_origin_accepted(mcp_client):
    """POST /mcp without Origin header returns 200 (same-origin)."""
    resp = mcp_client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 200

# -- TRANS-06: HTTP error responses -----------------------------

def test_wrong_path_returns_json_rpc_404(mcp_client):
    """POST /wrong returns 404 with JSON-RPC error body."""
    resp = mcp_client.post("/wrong", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 404
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert "error" in data
    assert data["error"]["message"] == "Not Found"

def test_wrong_method_returns_405(mcp_client):
    """PUT /mcp returns 405 Method Not Allowed."""
    resp = mcp_client.put("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 405

def test_wrong_accept_returns_406(mcp_client):
    """POST /mcp with Accept: text/html returns 406."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/html",
        "Mcp-Session-Id": mcp_client._session_id,
    }
    resp = mcp_client.post("/mcp", json=INIT_BODY, headers=headers)
    assert resp.status_code == 406
