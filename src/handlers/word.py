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

"""Word (.docx) handler — public API for all Word document operations.

This is the main entry point for Word operations. Delegates to:
- word_parser.py for .docx XML extraction
- word_location_validator.py for location validation
- word_writer.py for answer insertion
- word_fields.py for form field detection
"""

from __future__ import annotations

from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    BuildInsertionXmlResponse,
    ExtractStructureResponse,
    FormField,
    LocationSnippet,
    ValidatedLocation,
)
from src.xml_utils import (
    build_run_xml,
    extract_formatting,
    is_well_formed_ooxml,
)

from src.handlers.word_fields import (
    list_form_fields as _list_form_fields_impl,
)
from src.handlers.word_location_validator import (
    validate_locations,  # noqa: F401 — re-exported as public API
)
from src.handlers.word_parser import get_body_xml, read_document_xml
from src.handlers.word_writer import write_answers as _write_answers_impl


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Read a .docx and return the full <w:body> XML as a string."""
    body_xml = get_body_xml(file_bytes)
    return ExtractStructureResponse(body_xml=body_xml)


def build_insertion_xml(request: BuildInsertionXmlRequest) -> BuildInsertionXmlResponse:
    """Build a <w:r> element inheriting formatting from the target location.

    For plain_text: extract formatting from target_context_xml and wrap
    answer_text in a <w:r> with that formatting.

    For structured: validate the AI-provided OOXML.
    """
    if request.answer_type == AnswerType.PLAIN_TEXT:
        formatting = extract_formatting(request.target_context_xml)
        run_xml = build_run_xml(request.answer_text, formatting)
        return BuildInsertionXmlResponse(insertion_xml=run_xml, valid=True)

    elif request.answer_type == AnswerType.STRUCTURED:
        valid, error = is_well_formed_ooxml(request.answer_text)
        if valid:
            return BuildInsertionXmlResponse(
                insertion_xml=request.answer_text, valid=True
            )
        else:
            return BuildInsertionXmlResponse(
                insertion_xml="", valid=False, error=error
            )

    return BuildInsertionXmlResponse(
        insertion_xml="", valid=False,
        error=f"Unknown answer_type: {request.answer_type}",
    )


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Insert answers at the specified XPaths and return the modified .docx bytes."""
    doc_xml = read_document_xml(file_bytes)
    return _write_answers_impl(doc_xml, file_bytes, answers)


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Detect empty table cells and placeholder text as fillable targets."""
    doc_xml = read_document_xml(file_bytes)
    return _list_form_fields_impl(doc_xml)
