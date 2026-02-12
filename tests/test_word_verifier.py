"""Tests for the Word (.docx) output verifier."""

from pathlib import Path

import pytest
from lxml import etree

from src.handlers.word import extract_structure, write_answers
from src.handlers.word_verifier import verify_output
from src.models import (
    AnswerPayload,
    ContentStatus,
    ExpectedAnswer,
    InsertionMode,
)
from src.xml_utils import NAMESPACES

FIXTURES = Path(__file__).parent / "fixtures"
W = NAMESPACES["w"]


@pytest.fixture
def table_docx() -> bytes:
    return (FIXTURES / "table_questionnaire.docx").read_bytes()


@pytest.fixture
def filled_docx(table_docx: bytes) -> bytes:
    """A table_questionnaire.docx with two answers written into it."""
    answers = [
        AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[2]",
            insertion_xml=f'<w:r xmlns:w="{W}"><w:t>Acme Corporation</w:t></w:r>',
            mode=InsertionMode.REPLACE_CONTENT,
        ),
        AnswerPayload(
            pair_id="q2",
            xpath="./w:tbl[1]/w:tr[3]/w:tc[2]",
            insertion_xml=f'<w:r xmlns:w="{W}"><w:t>123 Main Street</w:t></w:r>',
            mode=InsertionMode.REPLACE_CONTENT,
        ),
    ]
    return write_answers(table_docx, answers)


class TestVerifyOutputContentAllMatched:
    def test_all_matched(self, filled_docx: bytes) -> None:
        """All expected answers match the actual content."""
        expected = [
            ExpectedAnswer(
                pair_id="q1",
                xpath="./w:tbl[1]/w:tr[2]/w:tc[2]",
                expected_text="Acme Corporation",
            ),
            ExpectedAnswer(
                pair_id="q2",
                xpath="./w:tbl[1]/w:tr[3]/w:tc[2]",
                expected_text="123 Main Street",
            ),
        ]
        report = verify_output(filled_docx, expected)

        assert report.summary.total == 2
        assert report.summary.matched == 2
        assert report.summary.mismatched == 0
        assert report.summary.missing == 0
        assert len(report.structural_issues) == 0

        for result in report.content_results:
            assert result.status == ContentStatus.MATCHED


class TestVerifyOutputContentMismatched:
    def test_one_mismatched(self, filled_docx: bytes) -> None:
        """One answer has wrong text — status should be mismatched."""
        expected = [
            ExpectedAnswer(
                pair_id="q1",
                xpath="./w:tbl[1]/w:tr[2]/w:tc[2]",
                expected_text="Acme Corporation",
            ),
            ExpectedAnswer(
                pair_id="q2",
                xpath="./w:tbl[1]/w:tr[3]/w:tc[2]",
                expected_text="WRONG TEXT NOT IN DOCUMENT",
            ),
        ]
        report = verify_output(filled_docx, expected)

        assert report.summary.matched == 1
        assert report.summary.mismatched == 1

        q2_result = next(r for r in report.content_results if r.pair_id == "q2")
        assert q2_result.status == ContentStatus.MISMATCHED
        assert q2_result.expected == "WRONG TEXT NOT IN DOCUMENT"
        assert "123 Main Street" in q2_result.actual


class TestVerifyOutputContentMissing:
    def test_missing_xpath(self, filled_docx: bytes) -> None:
        """XPath that doesn't exist — status should be missing."""
        expected = [
            ExpectedAnswer(
                pair_id="q1",
                xpath="./w:tbl[1]/w:tr[2]/w:tc[2]",
                expected_text="Acme Corporation",
            ),
            ExpectedAnswer(
                pair_id="q_bad",
                xpath="./w:tbl[99]/w:tr[1]/w:tc[1]",
                expected_text="Nonexistent",
            ),
        ]
        report = verify_output(filled_docx, expected)

        assert report.summary.matched == 1
        assert report.summary.missing == 1

        bad_result = next(r for r in report.content_results if r.pair_id == "q_bad")
        assert bad_result.status == ContentStatus.MISSING
        assert bad_result.actual == ""


class TestVerifyOutputStructuralIssues:
    def test_bare_run_under_tc_detected(self, table_docx: bytes) -> None:
        """A document with a bare w:r under w:tc should report a structural issue.

        We craft a malformed docx by manually inserting a bare run into a cell.
        """
        malformed = _make_malformed_docx(table_docx)
        report = verify_output(malformed, [])

        assert report.summary.structural_issues > 0
        assert any(
            "Bare <w:r>" in issue for issue in report.structural_issues
        )


class TestVerifyOutputEmptyExpected:
    def test_no_expected_answers(self, filled_docx: bytes) -> None:
        """Passing no expected answers should still run structural checks."""
        report = verify_output(filled_docx, [])

        assert report.summary.total == 0
        assert report.summary.matched == 0
        assert report.summary.structural_issues == 0
        assert len(report.content_results) == 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_malformed_docx(file_bytes: bytes) -> bytes:
    """Create a docx with a bare w:r directly under a w:tc (invalid OOXML).

    Takes a valid docx, parses document.xml, finds the first table cell,
    and appends a bare w:r element as a direct child of w:tc.
    """
    import zipfile
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        doc_xml = zf.read("word/document.xml")

    root = etree.fromstring(doc_xml)
    body = root.find("w:body", NAMESPACES)

    # Find first table cell and add a bare run (not wrapped in w:p)
    first_tc = body.find(".//w:tc", NAMESPACES)
    bare_run = etree.SubElement(first_tc, f"{{{W}}}r")
    bare_t = etree.SubElement(bare_run, f"{{{W}}}t")
    bare_t.text = "bare run"

    modified_xml = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    output = BytesIO()
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf_in:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                if item.filename == "word/document.xml":
                    zf_out.writestr(item, modified_xml)
                else:
                    zf_out.writestr(item, zf_in.read(item.filename))
    return output.getvalue()
