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
    Confidence,
    ContentResult,
    ContentStatus,
    ExpectedAnswer,
    VerificationReport,
    VerificationSummary,
)
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
        if answer.expected_text in actual_text:
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

    conf_counts = _count_confidence(expected_answers)

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
