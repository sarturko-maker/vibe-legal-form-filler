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

"""MCP tools for writing answers and verifying output.

These are the write-side tools in the pipeline. Each function is decorated
with @mcp.tool() to register it on the shared FastMCP instance.
"""

from __future__ import annotations

import base64
import json

from src.mcp_app import mcp
from src.handlers import excel as excel_handler
from src.handlers import pdf as pdf_handler
from src.handlers import word as word_handler
from src.handlers.excel_verifier import verify_output as excel_verify_output
from src.handlers.pdf_verifier import verify_output as pdf_verify_output
from src.handlers.word_verifier import verify_output as word_verify_output
from src.models import FileType
from src.tool_errors import (
    build_answer_payloads,
    resolve_file_for_tool,
    validate_expected_answers,
)
from src.validators import (
    MAX_ANSWERS,
    MAX_FILE_SIZE,
    validate_path_safe,
)


def _is_skip(payload) -> bool:
    """Return True if the answer is an intentional SKIP.

    Case-insensitive: "SKIP", "skip", "Skip" all match. The agent signals
    that a field should be left blank by setting answer_text to "SKIP".
    """
    return (
        payload.answer_text is not None
        and payload.answer_text.strip().upper() == "SKIP"
    )


def _resolve_answers_input(
    answers: list[dict] | None,
    answers_file_path: str,
) -> list[dict]:
    """Resolve answers from inline list or JSON file on disk.

    Prefer answers_file_path for large payloads (>20 answers) to avoid
    overwhelming the agent's context window. Falls back to inline answers.
    """
    if answers_file_path:
        path = validate_path_safe(answers_file_path)
        if not path.is_file():
            raise ValueError("Answers file not found or not accessible")
        if path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("Answers file exceeds maximum size")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("answers_file_path must contain a JSON array")
        if len(data) > MAX_ANSWERS:
            raise ValueError(
                f"Too many answers ({len(data)}). Max is {MAX_ANSWERS}."
            )
        return data

    if answers:
        if len(answers) > MAX_ANSWERS:
            raise ValueError(
                f"Too many answers ({len(answers)}). Max is {MAX_ANSWERS}."
            )
        return answers

    raise ValueError(
        "Provide either answers (inline) or answers_file_path. "
        "Neither was supplied."
    )


@mcp.tool()
def write_answers(
    answers: list[dict] | None = None,
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
    output_file_path: str = "",
    answers_file_path: str = "",
    dry_run: bool = False,
) -> dict:
    """Write all answers into the document and return the completed file bytes.

    file_path: path to the document on disk (preferred for interactive use).
    file_bytes_b64: base64-encoded file bytes (for programmatic use).
    answers: list of answer dicts. Each answer must have pair_id and exactly
        one of answer_text or insertion_xml:
        - answer_text: plain text answer (recommended). xpath and mode are
          optional -- the server resolves xpath from pair_id via re-extraction
          and defaults mode to replace_content.
        - insertion_xml: pre-built OOXML (legacy path). Requires explicit
          xpath and mode.
    answers_file_path: path to a JSON file containing the answers array.
        Use this instead of inline answers for large payloads (>20 answers)
        to avoid overwhelming the agent's context window.
    output_file_path: when provided, writes result to disk instead of returning b64.
    dry_run: when True, resolves all targets and returns a preview showing
        current cell content alongside what would be written, without modifying
        the document. Use this to catch 'right answer, wrong cell' errors
        before committing. Default: False.

    Returns {file_bytes_b64: ...} or {file_path: ...} when output_file_path is set.
    May include a 'warnings' key when pair_id cross-check detects mismatches.
    When dry_run=True, returns {preview: [...]} instead.
    """
    raw, ft = resolve_file_for_tool(
        "write_answers",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )

    answer_dicts = _resolve_answers_input(answers, answers_file_path)
    payloads, warnings = build_answer_payloads(answer_dicts, ft, raw)

    skipped = [p for p in payloads if _is_skip(p)]
    to_write = [p for p in payloads if not _is_skip(p)]

    if dry_run:
        result = _dry_run_preview(raw, ft, to_write)
        for p in skipped:
            result["preview"].append({
                "pair_id": p.pair_id,
                "xpath": p.xpath,
                "status": "skipped",
                "message": "Intentional SKIP -- field will not be written",
            })
        result["summary"] = {
            "written": len(to_write),
            "skipped": len(skipped),
        }
        return result

    if to_write:
        if ft == FileType.WORD:
            result_bytes = word_handler.write_answers(raw, to_write)
        elif ft == FileType.EXCEL:
            result_bytes = excel_handler.write_answers(raw, to_write)
        elif ft == FileType.PDF:
            result_bytes = pdf_handler.write_answers(raw, to_write)
        else:
            raise NotImplementedError(
                f"write_answers not yet implemented for {ft.value}"
            )
    else:
        result_bytes = raw  # All answers skipped, return original

    summary = {"written": len(to_write), "skipped": len(skipped)}

    if output_file_path:
        out = validate_path_safe(output_file_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(result_bytes)
        response: dict = {"file_path": str(out)}
        if warnings:
            response["warnings"] = warnings
        response["summary"] = summary
        return response

    response = {"file_bytes_b64": base64.b64encode(result_bytes).decode()}
    if warnings:
        response["warnings"] = warnings
    response["summary"] = summary
    return response


def _dry_run_preview(
    raw: bytes, ft: FileType, payloads: list
) -> dict:
    """Resolve all targets and return a preview without modifying the document."""
    if ft == FileType.WORD:
        from src.handlers.word_dry_run import preview_answers
        previews = preview_answers(raw, payloads)
    else:
        raise NotImplementedError(
            f"dry_run not yet implemented for {ft.value}"
        )
    return {"preview": previews, "dry_run": True}


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
    raw, ft = resolve_file_for_tool(
        "verify_output",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )
    answers, warnings, resolved_from_list = validate_expected_answers(
        expected_answers
    )

    if ft == FileType.WORD:
        return word_verify_output(raw, answers).model_dump()
    if ft == FileType.EXCEL:
        return excel_verify_output(raw, answers).model_dump()
    if ft == FileType.PDF:
        return pdf_verify_output(raw, answers).model_dump()

    raise NotImplementedError(
        f"verify_output not yet implemented for {ft.value}"
    )
