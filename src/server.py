"""MCP server entry point — tool registration and dispatch."""

from __future__ import annotations

import base64

from mcp.server.fastmcp import FastMCP

from src.handlers import word as word_handler
from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    FileType,
    InsertionMode,
    LocationSnippet,
)
from src.validators import validate_file_bytes, validate_file_type

mcp = FastMCP("form-filler")


# ── Tools ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def extract_structure(file_bytes_b64: str, file_type: str) -> dict:
    """Return the document structure so the calling agent can identify Q/A pairs.

    Word: full <w:body> XML.  Excel: JSON of sheets/rows/cells.  PDF: list of
    fillable field names, types, and current values.

    file_bytes_b64: base64-encoded file bytes.
    """
    ft = validate_file_type(file_type)
    raw = base64.b64decode(file_bytes_b64)
    validate_file_bytes(raw, ft)

    if ft == FileType.WORD:
        result = word_handler.extract_structure(raw)
        return {"body_xml": result.body_xml}

    raise NotImplementedError(f"extract_structure not yet implemented for {ft.value}")


@mcp.tool()
def validate_locations(
    file_bytes_b64: str, file_type: str, locations: list[dict]
) -> dict:
    """Confirm that each location snippet actually exists in the document.

    Returns match status and XPath/reference for each snippet.

    file_bytes_b64: base64-encoded file bytes.
    locations: list of {pair_id, snippet} dicts.
    """
    ft = validate_file_type(file_type)
    raw = base64.b64decode(file_bytes_b64)
    validate_file_bytes(raw, ft)

    if ft == FileType.WORD:
        locs = [LocationSnippet(**loc) for loc in locations]
        validated = word_handler.validate_locations(raw, locs)
        return {"validated": [v.model_dump() for v in validated]}

    raise NotImplementedError(f"validate_locations not yet implemented for {ft.value}")


@mcp.tool()
def build_insertion_xml(
    answer_text: str, target_context_xml: str, answer_type: str
) -> dict:
    """Build well-formed OOXML for inserting an answer (Word only).

    plain_text: code templates the XML inheriting formatting.
    structured: validates AI-provided OOXML.
    """
    at = AnswerType(answer_type)
    req = BuildInsertionXmlRequest(
        answer_text=answer_text,
        target_context_xml=target_context_xml,
        answer_type=at,
    )
    result = word_handler.build_insertion_xml(req)
    return result.model_dump()


@mcp.tool()
def write_answers(
    file_bytes_b64: str, file_type: str, answers: list[dict]
) -> dict:
    """Write all answers into the document and return the completed file bytes.

    file_bytes_b64: base64-encoded file bytes.
    answers: list of {pair_id, xpath, insertion_xml, mode} dicts.

    Returns {file_bytes_b64: base64-encoded result}.
    """
    ft = validate_file_type(file_type)
    raw = base64.b64decode(file_bytes_b64)
    validate_file_bytes(raw, ft)

    if ft == FileType.WORD:
        payloads = [
            AnswerPayload(
                pair_id=a["pair_id"],
                xpath=a["xpath"],
                insertion_xml=a["insertion_xml"],
                mode=InsertionMode(a["mode"]),
            )
            for a in answers
        ]
        result_bytes = word_handler.write_answers(raw, payloads)
        return {"file_bytes_b64": base64.b64encode(result_bytes).decode()}

    raise NotImplementedError(f"write_answers not yet implemented for {ft.value}")


@mcp.tool()
def list_form_fields(file_bytes_b64: str, file_type: str) -> dict:
    """Return a plain inventory of all fillable targets found by code (not AI).

    file_bytes_b64: base64-encoded file bytes.
    """
    ft = validate_file_type(file_type)
    raw = base64.b64decode(file_bytes_b64)
    validate_file_bytes(raw, ft)

    if ft == FileType.WORD:
        fields = word_handler.list_form_fields(raw)
        return {"fields": [f.model_dump() for f in fields]}

    raise NotImplementedError(f"list_form_fields not yet implemented for {ft.value}")
