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

"""Word (.docx) output verification — validate structure and content after writing.

Post-write verification tool. Checks that the filled document has valid OOXML
structure (no bare runs under table cells, every cell has a paragraph) and that
the expected answer text actually appears at each XPath location.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from lxml import etree

from src.models import (
    ContentResult,
    ContentStatus,
    ExpectedAnswer,
    VerificationReport,
    VerificationSummary,
)
from src.validators import count_confidence
from src.xml_utils import NAMESPACES

WORD_NAMESPACE_URI = NAMESPACES["w"]


def _read_document_xml(file_bytes: bytes) -> bytes:
    """Extract word/document.xml from a .docx ZIP archive."""
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        return zf.read("word/document.xml")


def _extract_text(element: etree._Element) -> str:
    """Extract concatenated text from all w:t elements under element."""
    texts: list[str] = []
    for t_elem in element.iter(f"{{{WORD_NAMESPACE_URI}}}t"):
        if t_elem.text:
            texts.append(t_elem.text)
    return " ".join(texts)


def _check_structural_issues(body: etree._Element) -> list[str]:
    """Check for OOXML structural violations in the document body.

    Detects:
    - Bare <w:r> directly under <w:tc> (runs must be inside paragraphs)
    - <w:tc> with no <w:p> child (every table cell needs at least one paragraph)
    """
    issues: list[str] = []

    for tc in body.iter(f"{{{WORD_NAMESPACE_URI}}}tc"):
        for child in tc:
            if child.tag == f"{{{WORD_NAMESPACE_URI}}}r":
                context = _extract_text(tc)[:50]
                issues.append(
                    f"Bare <w:r> found directly under <w:tc>"
                    f" (context: {context!r})"
                )

        paras = tc.findall(f"{{{WORD_NAMESPACE_URI}}}p")
        if not paras:
            context = _extract_text(tc)[:50]
            issues.append(
                f"<w:tc> has no <w:p> child (context: {context!r})"
            )

    return issues


def _verify_content(
    body: etree._Element, expected_answers: list[ExpectedAnswer]
) -> list[ContentResult]:
    """Compare expected text against actual text at each XPath."""
    results: list[ContentResult] = []

    for answer in expected_answers:
        matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
        if not matched:
            results.append(ContentResult(
                pair_id=answer.pair_id,
                status=ContentStatus.MISSING,
                expected=answer.expected_text,
                actual="",
            ))
            continue

        actual_text = _extract_text(matched[0])
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


def verify_output(
    file_bytes: bytes, expected_answers: list[ExpectedAnswer]
) -> VerificationReport:
    """Verify structural integrity and content of a filled document.

    file_bytes: the filled .docx file bytes.
    expected_answers: list of expected text at specific XPaths.

    Returns a report with structural issues, per-answer content results,
    and a summary with counts.
    """
    doc_xml = _read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")

    structural_issues = _check_structural_issues(body)
    content_results = _verify_content(body, expected_answers)

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
        structural_issues=len(structural_issues),
        **conf_counts,
    )

    return VerificationReport(
        structural_issues=structural_issues,
        content_results=content_results,
        summary=summary,
    )
