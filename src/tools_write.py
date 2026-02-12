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
from src.models import (
    AnswerPayload,
    ExpectedAnswer,
    FileType,
    InsertionMode,
)
from src.validators import (
    MAX_ANSWERS,
    MAX_FILE_SIZE,
    resolve_file_input,
    validate_path_safe,
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


def _build_payloads(answer_dicts: list[dict], ft: FileType) -> list[AnswerPayload]:
    """Build AnswerPayload objects from raw dicts, adapting field names per format."""
    if ft == FileType.WORD:
        return [
            AnswerPayload(
                pair_id=a["pair_id"],
                xpath=a["xpath"],
                insertion_xml=a["insertion_xml"],
                mode=InsertionMode(a["mode"]),
            )
            for a in answer_dicts
        ]

    # Excel and PDF use relaxed field names (cell_id/field_id, value)
    return [
        AnswerPayload(
            pair_id=a["pair_id"],
            xpath=a.get("xpath") or a.get("cell_id") or a.get("field_id", ""),
            insertion_xml=a.get("insertion_xml") or a.get("value", ""),
            mode=InsertionMode(
                a.get("mode", InsertionMode.REPLACE_CONTENT.value)
            ),
        )
        for a in answer_dicts
    ]


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
    payloads = _build_payloads(answer_dicts, ft)

    if ft == FileType.WORD:
        result_bytes = word_handler.write_answers(raw, payloads)
    elif ft == FileType.EXCEL:
        result_bytes = excel_handler.write_answers(raw, payloads)
    elif ft == FileType.PDF:
        result_bytes = pdf_handler.write_answers(raw, payloads)
    else:
        raise NotImplementedError(
            f"write_answers not yet implemented for {ft.value}"
        )

    if output_file_path:
        out = validate_path_safe(output_file_path)
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
        return word_verify_output(raw, answers).model_dump()
    if ft == FileType.EXCEL:
        answers = [ExpectedAnswer(**a) for a in expected_answers]
        return excel_verify_output(raw, answers).model_dump()
    if ft == FileType.PDF:
        answers = [ExpectedAnswer(**a) for a in expected_answers]
        return pdf_verify_output(raw, answers).model_dump()

    raise NotImplementedError(
        f"verify_output not yet implemented for {ft.value}"
    )
