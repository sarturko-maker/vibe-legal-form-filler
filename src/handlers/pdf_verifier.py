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

"""PDF output verification — reads widget values and compares to expected.

No structural validation needed (PyMuPDF handles PDF integrity).
Only content verification: read widget value at each field ID location,
compare to expected text (case-insensitive substring match).
"""

from __future__ import annotations

import fitz

from src.models import (
    ContentResult,
    ContentStatus,
    ExpectedAnswer,
    VerificationReport,
    VerificationSummary,
)
from src.validators import count_confidence


def verify_output(
    file_bytes: bytes, expected_answers: list[ExpectedAnswer]
) -> VerificationReport:
    """Verify that all expected answers appear in the filled PDF.

    file_bytes: the filled PDF bytes.
    expected_answers: list of expected text at specific field IDs.
    Returns a VerificationReport with content results and summary.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    content_results = _verify_content(doc, expected_answers)
    doc.close()

    matched = sum(1 for r in content_results if r.status == ContentStatus.MATCHED)
    mismatched = sum(
        1 for r in content_results if r.status == ContentStatus.MISMATCHED
    )
    missing = sum(1 for r in content_results if r.status == ContentStatus.MISSING)

    conf_counts = count_confidence(expected_answers)

    summary = VerificationSummary(
        total=len(expected_answers),
        matched=matched,
        mismatched=mismatched,
        missing=missing,
        structural_issues=0,
        **conf_counts,
    )

    return VerificationReport(
        structural_issues=[],
        content_results=content_results,
        summary=summary,
    )


def _verify_content(
    doc: fitz.Document, expected_answers: list[ExpectedAnswer]
) -> list[ContentResult]:
    """Compare expected text against actual widget values."""
    field_index = _build_value_index(doc)
    results: list[ContentResult] = []

    for answer in expected_answers:
        field_id = answer.xpath  # For PDF, xpath holds the F-ID
        if field_id not in field_index:
            results.append(ContentResult(
                pair_id=answer.pair_id,
                status=ContentStatus.MISSING,
                expected=answer.expected_text,
                actual="",
            ))
            continue

        actual_text = field_index[field_id]
        if answer.expected_text.lower() in actual_text.lower():
            status = ContentStatus.MATCHED
        else:
            status = ContentStatus.MISMATCHED

        results.append(ContentResult(
            pair_id=answer.pair_id,
            status=status,
            expected=answer.expected_text,
            actual=actual_text,
        ))

    return results


def _build_value_index(doc: fitz.Document) -> dict[str, str]:
    """Build a mapping from F-ID to current widget value.

    Iterates in the same deterministic order as the indexer and writer.
    """
    index: dict[str, str] = {}
    counter = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        for widget in page.widgets():
            counter += 1
            field_id = f"F{counter}"
            value = widget.field_value
            index[field_id] = str(value) if value is not None else ""

    return index
