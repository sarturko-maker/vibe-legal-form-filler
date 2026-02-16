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

"""HTTP transport runner with port conflict detection and graceful shutdown.

FastMCP's built-in ``mcp.run(transport='streamable-http')`` creates a uvicorn
server but does not pre-check whether the port is available and does not set
a graceful shutdown timeout.  This module provides both:

- ``check_port_available()`` — fail fast with a clear error instead of a
  cryptic uvicorn traceback when the port is already bound.
- ``start_http()`` — runs uvicorn with ``timeout_graceful_shutdown`` so
  in-flight requests are given time to complete on Ctrl-C.

The Starlette app is obtained from ``mcp.streamable_http_app()``, which
includes all registered MCP tools and DNS rebinding protection.
"""

import errno
import socket
import sys

import anyio
import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.mcp_app import mcp

GRACEFUL_SHUTDOWN_TIMEOUT = 5  # seconds


def check_port_available(host: str, port: int) -> bool:
    """Check if *host*:*port* is available for binding.

    Returns ``True`` if the port is free, ``False`` if it is already in use
    (``errno.EADDRINUSE``).  Any other ``OSError`` is re-raised.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            return False
        raise
    finally:
        sock.close()


async def _json_rpc_404_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a JSON-RPC error body for 404 Not Found.

    Starlette's default 404 returns plain text (``text/plain``).  MCP
    protocol compliance (TRANS-06) requires JSON-RPC error bodies on all
    error responses so that clients can parse failures uniformly.
    """
    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": "server-error",
            "error": {"code": -32600, "message": "Not Found"},
        },
        status_code=404,
    )


async def _run_http_async(host: str, port: int) -> None:
    """Start uvicorn serving the FastMCP Starlette app."""
    starlette_app = mcp.streamable_http_app()
    starlette_app.exception_handlers[404] = _json_rpc_404_handler
    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level=mcp.settings.log_level.lower(),
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT,
    )
    server = uvicorn.Server(config)
    await server.serve()


def start_http(host: str, port: int) -> None:
    """Check port availability, then start the HTTP server.

    Prints a user-friendly error and exits non-zero if the port is in use.
    Otherwise hands off to uvicorn via ``anyio.run()``.
    """
    if not check_port_available(host, port):
        print(
            f"Error: Port {port} is already in use. Try: --port {port + 1}",
            file=sys.stderr,
        )
        sys.exit(1)
    anyio.run(_run_http_async, host, port)
