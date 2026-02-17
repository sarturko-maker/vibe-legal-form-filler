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

"""MCP tools for extracting structure, validating locations, building XML,
and listing form fields.

These are the read-only and transform tools in the pipeline. Each function
is decorated with @mcp.tool() to register it on the shared FastMCP instance.
"""

from __future__ import annotations

from src.mcp_app import mcp
from src.handlers import excel as excel_handler
from src.handlers import pdf as pdf_handler
from src.handlers import word as word_handler
from src.handlers.excel_indexer import (
    extract_structure_compact as excel_extract_compact,
)
from src.handlers.pdf_indexer import (
    extract_structure_compact as pdf_extract_compact,
)
from src.handlers.word_indexer import (
    extract_structure_compact as word_extract_compact,
)
from src.models import (
    BuildInsertionXmlRequest,
    FileType,
)
from src.tool_errors import (
    resolve_file_for_tool,
    validate_answer_type,
    validate_location_snippets,
)


@mcp.tool()
def extract_structure_compact(
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Return a compact, indexed representation of the document structure.

    Walks the document body and assigns stable element IDs (T1-R2-C1 for
    table cells, P5 for paragraphs). Includes formatting hints, marks
    answer targets, and flags complex elements.

    This is the primary extraction tool — response is a few KB, not 134KB.

    Use this on the form/questionnaire you want to fill. For reference or
    knowledge documents, the agent should read them using its own file
    tools, not this MCP tool.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    Provide one or the other. file_type is auto-inferred from file_path extension.
    """
    raw, ft = resolve_file_for_tool(
        "extract_structure_compact",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )

    if ft == FileType.WORD:
        return word_extract_compact(raw).model_dump()
    if ft == FileType.EXCEL:
        return excel_extract_compact(raw).model_dump()
    if ft == FileType.PDF:
        return pdf_extract_compact(raw).model_dump()

    raise NotImplementedError(
        f"extract_structure_compact not yet implemented for {ft.value}"
    )


@mcp.tool()
def extract_structure(
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Return the document structure so the calling agent can identify Q/A pairs.

    Word: full <w:body> XML.  Excel: JSON of sheets/rows/cells.  PDF: list of
    fillable field names, types, and current values.

    Use this on the form/questionnaire you want to fill. For reference or
    knowledge documents, the agent should read them using its own file
    tools, not this MCP tool.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    """
    raw, ft = resolve_file_for_tool(
        "extract_structure",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )

    if ft == FileType.WORD:
        result = word_handler.extract_structure(raw)
        return {"body_xml": result.body_xml}
    if ft == FileType.EXCEL:
        result = excel_handler.extract_structure(raw)
        return {"sheets_json": result.sheets_json}
    if ft == FileType.PDF:
        result = pdf_handler.extract_structure(raw)
        return {"fields": [f.model_dump() for f in result.fields]}

    raise NotImplementedError(
        f"extract_structure not yet implemented for {ft.value}"
    )


@mcp.tool()
def validate_locations(
    locations: list[dict],
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Confirm that each location snippet actually exists in the document.

    Returns match status and XPath/reference for each snippet.
    Use on the form being filled, not on reference documents.

    locations: list of {pair_id, snippet} dicts.
    """
    raw, ft = resolve_file_for_tool(
        "validate_locations",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )
    locs = validate_location_snippets(locations)

    if ft == FileType.WORD:
        validated = word_handler.validate_locations(raw, locs)
    elif ft == FileType.EXCEL:
        validated = excel_handler.validate_locations(raw, locs)
    elif ft == FileType.PDF:
        validated = pdf_handler.validate_locations(raw, locs)
    else:
        raise NotImplementedError(
            f"validate_locations not yet implemented for {ft.value}"
        )

    return {"validated": [v.model_dump() for v in validated]}


@mcp.tool()
def build_insertion_xml(
    answer_text: str, target_context_xml: str, answer_type: str
) -> dict:
    """Build well-formed OOXML for inserting an answer (Word only).

    plain_text: code templates the XML inheriting formatting.
    structured: validates AI-provided OOXML.
    """
    at = validate_answer_type(answer_type)
    req = BuildInsertionXmlRequest(
        answer_text=answer_text,
        target_context_xml=target_context_xml,
        answer_type=at,
    )
    result = word_handler.build_insertion_xml(req)
    return result.model_dump()


@mcp.tool()
def list_form_fields(
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Return a plain inventory of all fillable targets found by code (not AI).

    Use on the form being filled, not on reference documents.
    """
    raw, ft = resolve_file_for_tool(
        "list_form_fields",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )

    if ft == FileType.WORD:
        fields = word_handler.list_form_fields(raw)
    elif ft == FileType.EXCEL:
        fields = excel_handler.list_form_fields(raw)
    elif ft == FileType.PDF:
        fields = pdf_handler.list_form_fields(raw)
    else:
        raise NotImplementedError(
            f"list_form_fields not yet implemented for {ft.value}"
        )

    return {"fields": [f.model_dump() for f in fields]}
