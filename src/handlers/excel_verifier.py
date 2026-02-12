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
    Confidence,
    ContentResult,
    ContentStatus,
    ExpectedAnswer,
    VerificationReport,
    VerificationSummary,
)


def _count_confidence(expected_answers: list[ExpectedAnswer]) -> dict:
    """Count confidence levels and build a summary note."""
    known = sum(1 for a in expected_answers if a.confidence == Confidence.KNOWN)
    uncertain = sum(1 for a in expected_answers if a.confidence == Confidence.UNCERTAIN)
    unknown = sum(1 for a in expected_answers if a.confidence == Confidence.UNKNOWN)

    parts = []
    if known:
        parts.append(f"{known} known")
    if uncertain:
        parts.append(f"{uncertain} uncertain")
    if unknown:
        parts.append(f"{unknown} unknown")
    note = ", ".join(parts)
    if uncertain or unknown:
        note += " — manual review needed"

    return {
        "confidence_known": known,
        "confidence_uncertain": uncertain,
        "confidence_unknown": unknown,
        "confidence_note": note,
    }


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

    matched = sum(1 for r in content_results if r.status == ContentStatus.MATCHED)
    mismatched = sum(
        1 for r in content_results if r.status == ContentStatus.MISMATCHED
    )
    missing = sum(1 for r in content_results if r.status == ContentStatus.MISSING)

    conf_counts = _count_confidence(expected_answers)

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
