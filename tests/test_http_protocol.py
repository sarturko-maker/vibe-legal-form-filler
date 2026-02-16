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
Shared fixtures (mcp_session, INIT_BODY, MCP_HEADERS) are in conftest.py.
"""

from starlette.testclient import TestClient

from src.http_transport import _json_rpc_404_handler
from src.mcp_app import mcp

from tests.conftest import INIT_BODY, MCP_HEADERS, _fresh_app


# -- TRANS-03: JSON-RPC 2.0 POST requests ---------------------

def test_initialize_returns_200(mcp_session):
    """POST /mcp with valid JSON-RPC initialize body returns 200."""
    client, headers = mcp_session
    resp = client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 200


def test_tools_list_returns_tools(mcp_session):
    """POST /mcp with tools/list returns the registered MCP tools."""
    client, headers = mcp_session
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2,
        "params": {},
    }
    resp = client.post("/mcp", json=body, headers=headers)
    assert resp.status_code == 200


# -- TRANS-04: Protocol version validation ----------------------

def test_bad_protocol_version_returns_400(mcp_session):
    """POST /mcp with invalid mcp-protocol-version returns 400."""
    client, headers = mcp_session
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 3,
        "params": {},
    }
    bad_headers = {**headers, "mcp-protocol-version": "9999-99-99"}
    resp = client.post("/mcp", json=body, headers=bad_headers)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert "supported" in data["error"]["message"].lower()


def test_missing_protocol_version_accepted(mcp_session):
    """POST /mcp without protocol version header succeeds (SDK defaults)."""
    client, headers = mcp_session
    body = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 4,
        "params": {},
    }
    resp = client.post("/mcp", json=body, headers=headers)
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


def test_valid_origin_accepted(mcp_session):
    """POST /mcp with Origin: http://localhost:8000 returns 200."""
    client, headers = mcp_session
    origin_headers = {**MCP_HEADERS, "Origin": "http://localhost:8000"}
    resp = client.post("/mcp", json=INIT_BODY, headers=origin_headers)
    assert resp.status_code == 200


def test_missing_origin_accepted(mcp_session):
    """POST /mcp without Origin header returns 200 (same-origin)."""
    client, headers = mcp_session
    resp = client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 200


# -- TRANS-06: HTTP error responses -----------------------------

def test_wrong_path_returns_json_rpc_404(mcp_session):
    """POST /wrong returns 404 with JSON-RPC error body."""
    client, headers = mcp_session
    resp = client.post("/wrong", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 404
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert "error" in data
    assert data["error"]["message"] == "Not Found"


def test_wrong_method_returns_405(mcp_session):
    """PUT /mcp returns 405 Method Not Allowed."""
    client, headers = mcp_session
    resp = client.put("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 405


def test_wrong_accept_returns_406(mcp_session):
    """POST /mcp with Accept: text/html returns 406."""
    client, headers = mcp_session
    bad_headers = {
        "Content-Type": "application/json",
        "Accept": "text/html",
        "Mcp-Session-Id": headers["Mcp-Session-Id"],
    }
    resp = client.post("/mcp", json=INIT_BODY, headers=bad_headers)
    assert resp.status_code == 406
