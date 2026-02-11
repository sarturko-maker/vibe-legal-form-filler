"""MCP server entry point — tool registration and dispatch."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.models import (
    AnswerType,
    BuildInsertionXmlRequest,
    BuildInsertionXmlResponse,
    ExtractStructureRequest,
    ExtractStructureResponse,
    FileType,
    ListFormFieldsRequest,
    ListFormFieldsResponse,
    ValidateLocationsRequest,
    ValidateLocationsResponse,
    WriteAnswersRequest,
    WriteAnswersResponse,
)

mcp = FastMCP("form-filler")


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def extract_structure(file_bytes: bytes, file_type: str) -> dict:
    """Return the document structure so the calling agent can identify Q/A pairs.

    Word: full <w:body> XML.  Excel: JSON of sheets/rows/cells.  PDF: list of
    fillable field names, types, and current values.
    """
    raise NotImplementedError


@mcp.tool()
def validate_locations(file_bytes: bytes, file_type: str, locations: list[dict]) -> dict:
    """Confirm that each location snippet actually exists in the document.

    Returns match status and XPath/reference for each snippet.
    """
    raise NotImplementedError


@mcp.tool()
def build_insertion_xml(answer_text: str, target_context_xml: str, answer_type: str) -> dict:
    """Build well-formed OOXML for inserting an answer (Word only).

    plain_text: code templates the XML inheriting formatting.
    structured: validates AI-provided OOXML.
    """
    raise NotImplementedError


@mcp.tool()
def write_answers(file_bytes: bytes, file_type: str, answers: list[dict]) -> dict:
    """Write all answers into the document and return the completed file bytes."""
    raise NotImplementedError


@mcp.tool()
def list_form_fields(file_bytes: bytes, file_type: str) -> dict:
    """Return a plain inventory of all fillable targets found by code (not AI)."""
    raise NotImplementedError
