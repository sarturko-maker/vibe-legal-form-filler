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

"""MCP server entry point — CLI parsing, transport dispatch, tool registration.

Tool functions are defined in tools_extract.py and tools_write.py, each
decorated with @mcp.tool() on the shared FastMCP instance from mcp_app.py.
Importing those modules here triggers tool registration at import time.

This module re-exports all tool function names so that existing imports
like ``from src.server import extract_structure_compact`` continue to work.

CLI flags:
    --transport {stdio,http}  Transport protocol (default: stdio)
    --port PORT               Port for HTTP transport (default: 8000)
    --host HOST               Host for HTTP transport (default: 127.0.0.1)

Environment variable fallbacks:
    MCP_FORM_FILLER_TRANSPORT, MCP_FORM_FILLER_PORT, MCP_FORM_FILLER_HOST
"""

import argparse
import os
import sys

from src.mcp_app import mcp  # noqa: F401

# Tool registration — importing these modules registers @mcp.tool() decorators
from src.tools_extract import (  # noqa: F401
    build_insertion_xml,
    extract_structure,
    extract_structure_compact,
    list_form_fields,
    validate_locations,
)
from src.tools_write import (  # noqa: F401
    verify_output,
    write_answers,
)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _validate_port(value: str) -> int:
    """Convert *value* to int and reject ports outside 1024-65535."""
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Port must be an integer, got {value!r}"
        )
    if port < 1024 or port > 65535:
        raise argparse.ArgumentTypeError(
            f"Port must be between 1024 and 65535, got {port}"
        )
    return port


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with --transport, --port, --host flags."""
    parser = argparse.ArgumentParser(
        prog="mcp-form-filler",
        description="MCP server exposing form-filling tools for copilot agents",
        epilog=(
            "Examples:\n"
            "  mcp-form-filler                              "
            "# stdio (default)\n"
            "  mcp-form-filler --transport http              "
            "# HTTP on 127.0.0.1:8000\n"
            "  mcp-form-filler --transport http --port 9000  "
            "# HTTP on custom port\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("MCP_FORM_FILLER_TRANSPORT", "stdio"),
        help=(
            "Transport protocol (default: stdio). "
            "Env: MCP_FORM_FILLER_TRANSPORT"
        ),
    )
    parser.add_argument(
        "--port",
        type=_validate_port,
        default=None,
        help=(
            "Port for HTTP transport (default: 8000). "
            "Env: MCP_FORM_FILLER_PORT"
        ),
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            "Host for HTTP transport (default: 127.0.0.1). "
            "Env: MCP_FORM_FILLER_HOST"
        ),
    )
    return parser


def _resolve_args(args: argparse.Namespace) -> argparse.Namespace:
    """Validate cross-flag constraints and resolve env var fallbacks.

    - Rejects --port/--host when --transport is not http.
    - Fills in port and host from env vars or defaults for HTTP mode.
    """
    if args.transport != "http" and (args.port is not None
                                     or args.host is not None):
        print(
            "Error: --port and --host require --transport http",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.transport == "http":
        if args.port is None:
            raw = os.environ.get("MCP_FORM_FILLER_PORT", "8000")
            try:
                args.port = _validate_port(raw)
            except argparse.ArgumentTypeError as exc:
                print(f"Error: MCP_FORM_FILLER_PORT: {exc}", file=sys.stderr)
                sys.exit(2)
        if args.host is None:
            args.host = os.environ.get("MCP_FORM_FILLER_HOST", "127.0.0.1")

    return args


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI args and dispatch to the chosen transport."""
    args = _resolve_args(_build_parser().parse_args())

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        from src.http_transport import start_http
        start_http(args.host, args.port)


if __name__ == "__main__":
    main()
