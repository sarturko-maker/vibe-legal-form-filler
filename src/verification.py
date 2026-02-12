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

"""Post-write verification helpers — confidence counting and summary building.

Shared by word_verifier, excel_verifier, and pdf_verifier to build
consistent VerificationSummary results after write_answers.
"""

from __future__ import annotations

from src.models import (
    Confidence,
    ContentResult,
    ContentStatus,
    ExpectedAnswer,
    VerificationSummary,
)


def count_confidence(expected_answers: list) -> dict:
    """Count confidence levels across expected answers and build a summary note.

    Works with any list of objects that have a .confidence attribute
    (e.g. ExpectedAnswer). Returns a dict with confidence_known,
    confidence_uncertain, confidence_unknown, and confidence_note.
    """
    known = sum(1 for a in expected_answers if a.confidence == Confidence.KNOWN)
    uncertain = sum(
        1 for a in expected_answers if a.confidence == Confidence.UNCERTAIN
    )
    unknown = sum(
        1 for a in expected_answers if a.confidence == Confidence.UNKNOWN
    )

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


def build_verification_summary(
    content_results: list[ContentResult],
    expected_answers: list[ExpectedAnswer],
    structural_issues_count: int = 0,
) -> VerificationSummary:
    """Build a VerificationSummary from content results and expected answers.

    Counts matched/mismatched/missing statuses and confidence levels.
    Shared across word, excel, and pdf verifiers.
    """
    matched = sum(1 for r in content_results if r.status == ContentStatus.MATCHED)
    mismatched = sum(
        1 for r in content_results if r.status == ContentStatus.MISMATCHED
    )
    missing = sum(1 for r in content_results if r.status == ContentStatus.MISSING)

    conf_counts = count_confidence(expected_answers)

    return VerificationSummary(
        total=len(expected_answers),
        matched=matched,
        mismatched=mismatched,
        missing=missing,
        structural_issues=structural_issues_count,
        **conf_counts,
    )
