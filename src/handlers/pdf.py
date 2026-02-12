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

"""PDF handler (fillable AcroForm only) — thin entry point.

Delegates to pdf_indexer for compact extraction, pdf_writer for writing,
pdf_verifier for verification. Uses PyMuPDF (fitz) for all operations.
"""

from __future__ import annotations

import fitz

from src.handlers.pdf_indexer import (
    _map_widget_type,
    extract_structure_compact,  # noqa: F401 — re-exported
)
from src.handlers.pdf_verifier import (
    verify_output,  # noqa: F401 — re-exported
)
from src.handlers.pdf_writer import write_answers as _write_answers_raw
from src.models import (
    AnswerPayload,
    ExtractStructureResponse,
    FormField,
    LocationSnippet,
    LocationStatus,
    ValidatedLocation,
)


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Return all AcroForm fields as a JSON list with types and values."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    fields = _collect_field_dicts(doc)
    doc.close()
    return ExtractStructureResponse(fields=[
        FormField(
            field_id=f["field_id"],
            label=f["native_name"],
            field_type=f["field_type"],
            current_value=f["value"] or None,
        )
        for f in fields
    ])


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Confirm that each field ID exists in the PDF.

    Accepts F-IDs (e.g. "F1", "F2") from extract_structure_compact.
    Re-derives the F-ID → native name mapping by scanning widgets in
    the same deterministic page order as the indexer.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    field_map = _build_field_map(doc)
    doc.close()

    results: list[ValidatedLocation] = []
    for loc in locations:
        field_id = loc.snippet
        if field_id in field_map:
            info = field_map[field_id]
            context = f"{info['native_name']} ({info['field_type']})"
            results.append(ValidatedLocation(
                pair_id=loc.pair_id,
                status=LocationStatus.MATCHED,
                xpath=field_id,
                context=context,
            ))
        else:
            results.append(ValidatedLocation(
                pair_id=loc.pair_id,
                status=LocationStatus.NOT_FOUND,
            ))

    return results


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Write values to PDF form fields and return modified bytes.

    For PDF, xpath holds the F-ID and insertion_xml holds the value.
    """
    answer_dicts = [
        {"field_id": a.xpath, "value": a.insertion_xml}
        for a in answers
    ]
    return _write_answers_raw(file_bytes, answer_dicts)


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Return all AcroForm fields with types and current values.

    Simpler than extract_structure_compact — no nearby text extraction.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    fields = _collect_field_dicts(doc)
    doc.close()
    return [
        FormField(
            field_id=f["field_id"],
            label=f["native_name"],
            field_type=f["field_type"],
            current_value=f["value"] or None,
        )
        for f in fields
    ]


def _build_field_map(doc: fitz.Document) -> dict[str, dict]:
    """Build F-ID → field info mapping in deterministic page order."""
    field_map: dict[str, dict] = {}
    counter = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        for widget in page.widgets():
            counter += 1
            field_id = f"F{counter}"
            field_map[field_id] = {
                "native_name": widget.field_name or f"unnamed_{counter}",
                "field_type": _map_widget_type(widget.field_type),
            }

    return field_map


def _collect_field_dicts(doc: fitz.Document) -> list[dict]:
    """Collect basic field info (no nearby text) for all widgets."""
    fields: list[dict] = []
    counter = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        for widget in page.widgets():
            counter += 1
            fields.append({
                "field_id": f"F{counter}",
                "native_name": widget.field_name or f"unnamed_{counter}",
                "field_type": _map_widget_type(widget.field_type),
                "value": str(widget.field_value) if widget.field_value else "",
            })

    return fields



# _map_widget_type imported from pdf_indexer (single source of truth)
