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

"""MCP server entry point — imports tool modules and runs the server.

Tool functions are defined in tools_extract.py and tools_write.py, each
decorated with @mcp.tool() on the shared FastMCP instance from mcp_app.py.
Importing those modules here triggers tool registration at import time.

This module re-exports all tool function names so that existing imports
like ``from src.server import extract_structure_compact`` continue to work.
"""

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


if __name__ == "__main__":
    mcp.run()
