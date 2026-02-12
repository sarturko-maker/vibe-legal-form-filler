"""MCP server entry point — tool registration and dispatch."""

from __future__ import annotations

import base64
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.handlers import word as word_handler
from src.handlers.word_indexer import (
    extract_structure_compact as word_extract_compact,
)
from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    FileType,
    InsertionMode,
    LocationSnippet,
)
from src.validators import resolve_file_input

mcp = FastMCP("form-filler")


# ── Tools ──────────────────────────────────────────────────────────────────────


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

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    Provide one or the other. file_type is auto-inferred from file_path extension.
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

    if ft == FileType.WORD:
        result = word_extract_compact(raw)
        return result.model_dump()

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

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    Provide one or the other. file_type is auto-inferred from file_path extension.
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

    if ft == FileType.WORD:
        result = word_handler.extract_structure(raw)
        return {"body_xml": result.body_xml}

    raise NotImplementedError(f"extract_structure not yet implemented for {ft.value}")


@mcp.tool()
def validate_locations(
    locations: list[dict],
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Confirm that each location snippet actually exists in the document.

    Returns match status and XPath/reference for each snippet.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    locations: list of {pair_id, snippet} dicts.
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

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
    answers: list[dict],
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
    output_file_path: str = "",
) -> dict:
    """Write all answers into the document and return the completed file bytes.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    answers: list of {pair_id, xpath, insertion_xml, mode} dicts.
    output_file_path: when provided, writes result to disk instead of returning b64.

    Returns {file_bytes_b64: ...} or {file_path: ...} when output_file_path is set.
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

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

        if output_file_path:
            out = Path(output_file_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(result_bytes)
            return {"file_path": str(out)}

        return {"file_bytes_b64": base64.b64encode(result_bytes).decode()}

    raise NotImplementedError(f"write_answers not yet implemented for {ft.value}")


@mcp.tool()
def list_form_fields(
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Return a plain inventory of all fillable targets found by code (not AI).

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

    if ft == FileType.WORD:
        fields = word_handler.list_form_fields(raw)
        return {"fields": [f.model_dump() for f in fields]}

    raise NotImplementedError(f"list_form_fields not yet implemented for {ft.value}")


if __name__ == "__main__":
    mcp.run()
