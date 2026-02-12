"""MCP server entry point — tool registration and dispatch."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.handlers import excel as excel_handler
from src.handlers import pdf as pdf_handler
from src.handlers import word as word_handler
from src.handlers.excel_indexer import (
    extract_structure_compact as excel_extract_compact,
)
from src.handlers.excel_verifier import verify_output as excel_verify_output
from src.handlers.pdf_indexer import (
    extract_structure_compact as pdf_extract_compact,
)
from src.handlers.pdf_verifier import verify_output as pdf_verify_output
from src.handlers.word_indexer import (
    extract_structure_compact as word_extract_compact,
)
from src.handlers.word_verifier import verify_output as word_verify_output
from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    ExpectedAnswer,
    FileType,
    InsertionMode,
    LocationSnippet,
)
from src.validators import resolve_file_input

mcp = FastMCP("form-filler")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _resolve_answers_input(
    answers: list[dict] | None,
    answers_file_path: str,
) -> list[dict]:
    """Resolve answers from inline list or JSON file on disk.

    Prefer answers_file_path for large payloads (>20 answers) to avoid
    overwhelming the agent's context window. Falls back to inline answers.
    """
    if answers_file_path:
        path = Path(answers_file_path)
        if not path.is_file():
            raise ValueError(f"answers_file_path not found: {answers_file_path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("answers_file_path must contain a JSON array")
        return data

    if answers:
        return answers

    raise ValueError(
        "Provide either answers (inline) or answers_file_path. "
        "Neither was supplied."
    )


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

    Use this on the form/questionnaire you want to fill. For reference or
    knowledge documents, the agent should read them using its own file
    tools, not this MCP tool.

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

    if ft == FileType.EXCEL:
        result = excel_extract_compact(raw)
        return result.model_dump()

    if ft == FileType.PDF:
        result = pdf_extract_compact(raw)
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

    Use this on the form/questionnaire you want to fill. For reference or
    knowledge documents, the agent should read them using its own file
    tools, not this MCP tool.

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

    if ft == FileType.EXCEL:
        result = excel_handler.extract_structure(raw)
        return {"sheets_json": result.sheets_json}

    if ft == FileType.PDF:
        result = pdf_handler.extract_structure(raw)
        return {"fields": [f.model_dump() for f in result.fields]}

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
    Use on the form being filled, not on reference documents.

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

    if ft == FileType.EXCEL:
        locs = [LocationSnippet(**loc) for loc in locations]
        validated = excel_handler.validate_locations(raw, locs)
        return {"validated": [v.model_dump() for v in validated]}

    if ft == FileType.PDF:
        locs = [LocationSnippet(**loc) for loc in locations]
        validated = pdf_handler.validate_locations(raw, locs)
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
    answers: list[dict] | None = None,
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
    output_file_path: str = "",
    answers_file_path: str = "",
) -> dict:
    """Write all answers into the document and return the completed file bytes.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    answers: list of {pair_id, xpath, insertion_xml, mode} dicts.
    answers_file_path: path to a JSON file containing the answers array.
        Use this instead of inline answers for large payloads (>20 answers)
        to avoid overwhelming the agent's context window.
    output_file_path: when provided, writes result to disk instead of returning b64.

    Returns {file_bytes_b64: ...} or {file_path: ...} when output_file_path is set.
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

    answer_dicts = _resolve_answers_input(answers, answers_file_path)

    if ft == FileType.WORD:
        payloads = [
            AnswerPayload(
                pair_id=a["pair_id"],
                xpath=a["xpath"],
                insertion_xml=a["insertion_xml"],
                mode=InsertionMode(a["mode"]),
            )
            for a in answer_dicts
        ]
        result_bytes = word_handler.write_answers(raw, payloads)

    elif ft == FileType.EXCEL:
        payloads = [
            AnswerPayload(
                pair_id=a["pair_id"],
                xpath=a.get("xpath") or a.get("cell_id", ""),
                insertion_xml=a.get("insertion_xml") or a.get("value", ""),
                mode=InsertionMode(
                    a.get("mode", InsertionMode.REPLACE_CONTENT.value)
                ),
            )
            for a in answer_dicts
        ]
        result_bytes = excel_handler.write_answers(raw, payloads)

    elif ft == FileType.PDF:
        payloads = [
            AnswerPayload(
                pair_id=a["pair_id"],
                xpath=a.get("xpath") or a.get("field_id", ""),
                insertion_xml=a.get("insertion_xml") or a.get("value", ""),
                mode=InsertionMode(
                    a.get("mode", InsertionMode.REPLACE_CONTENT.value)
                ),
            )
            for a in answer_dicts
        ]
        result_bytes = pdf_handler.write_answers(raw, payloads)

    else:
        raise NotImplementedError(
            f"write_answers not yet implemented for {ft.value}"
        )

    if output_file_path:
        out = Path(output_file_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(result_bytes)
        return {"file_path": str(out)}

    return {"file_bytes_b64": base64.b64encode(result_bytes).decode()}


@mcp.tool()
def verify_output(
    expected_answers: list[dict],
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Verify structural integrity and content of a filled document.

    Runs structural validation (OOXML well-formedness) and content verification
    (compare expected text vs actual at each XPath). Use after write_answers
    to confirm the output is correct.

    file_path: path to the filled document on disk.
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    expected_answers: list of {pair_id, xpath, expected_text} dicts.
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

    if ft == FileType.WORD:
        answers = [ExpectedAnswer(**a) for a in expected_answers]
        report = word_verify_output(raw, answers)
        return report.model_dump()

    if ft == FileType.EXCEL:
        answers = [ExpectedAnswer(**a) for a in expected_answers]
        report = excel_verify_output(raw, answers)
        return report.model_dump()

    if ft == FileType.PDF:
        answers = [ExpectedAnswer(**a) for a in expected_answers]
        report = pdf_verify_output(raw, answers)
        return report.model_dump()

    raise NotImplementedError(f"verify_output not yet implemented for {ft.value}")


@mcp.tool()
def list_form_fields(
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    """Return a plain inventory of all fillable targets found by code (not AI).

    Use on the form being filled, not on reference documents.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    """
    raw, ft = resolve_file_input(
        file_bytes_b64 or None, file_type or None, file_path or None
    )

    if ft == FileType.WORD:
        fields = word_handler.list_form_fields(raw)
        return {"fields": [f.model_dump() for f in fields]}

    if ft == FileType.EXCEL:
        fields = excel_handler.list_form_fields(raw)
        return {"fields": [f.model_dump() for f in fields]}

    if ft == FileType.PDF:
        fields = pdf_handler.list_form_fields(raw)
        return {"fields": [f.model_dump() for f in fields]}

    raise NotImplementedError(f"list_form_fields not yet implemented for {ft.value}")


if __name__ == "__main__":
    mcp.run()
