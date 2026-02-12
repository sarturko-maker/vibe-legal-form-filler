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

"""Excel (.xlsx) output verification — reads cells and compares to expected values.

Post-write verification tool. No structural validation needed for Excel
(openpyxl guarantees valid .xlsx output). Only content verification:
read cell value at each location, compare to expected text (substring match).
"""

from __future__ import annotations

from io import BytesIO

import openpyxl

from src.handlers.excel_writer import _parse_cell_id
from src.models import (
    ContentResult,
    ContentStatus,
    ExpectedAnswer,
    VerificationReport,
)
from src.verification import build_verification_summary


def verify_output(
    file_bytes: bytes, expected_answers: list[ExpectedAnswer]
) -> VerificationReport:
    """Verify that all expected answers appear in the filled workbook.

    file_bytes: the filled .xlsx file bytes.
    expected_answers: list of expected text at specific cell IDs.
    Returns a VerificationReport with content results and summary.
    """
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    content_results = _verify_content(wb, expected_answers)
    wb.close()

    summary = build_verification_summary(content_results, expected_answers)

    return VerificationReport(
        structural_issues=[],
        content_results=content_results,
        summary=summary,
    )


def _verify_content(
    wb: openpyxl.Workbook, expected_answers: list[ExpectedAnswer]
) -> list[ContentResult]:
    """Compare expected text against actual cell values."""
    results: list[ContentResult] = []

    for answer in expected_answers:
        cell_id = answer.xpath
        try:
            sheet_idx, row, col = _parse_cell_id(cell_id)
        except ValueError:
            results.append(ContentResult(
                pair_id=answer.pair_id,
                status=ContentStatus.MISSING,
                expected=answer.expected_text,
                actual=f"Invalid cell ID: {cell_id}",
            ))
            continue

        if sheet_idx < 1 or sheet_idx > len(wb.worksheets):
            results.append(ContentResult(
                pair_id=answer.pair_id,
                status=ContentStatus.MISSING,
                expected=answer.expected_text,
                actual="",
            ))
            continue

        ws = wb.worksheets[sheet_idx - 1]
        cell_value = ws.cell(row=row, column=col).value
        actual_text = str(cell_value) if cell_value is not None else ""

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
