"""Tests for the three-layer cell-safety system.

Layer 1: Role indicators in extract_structure_compact output.
Layer 2: Suspicious-write warnings in validate_locations.
Layer 3: dry_run preview in write_answers.
"""

from pathlib import Path

import pytest

from src.handlers.word_indexer import extract_structure_compact
from src.handlers.word_location_validator import validate_locations
from src.handlers.word_dry_run import preview_answers
from src.models import (
    AnswerPayload,
    InsertionMode,
    LocationSnippet,
    LocationStatus,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def table_docx() -> bytes:
    return (FIXTURES / "table_questionnaire.docx").read_bytes()


# ── Layer 1: Role indicators ────────────────────────────────────────────────


class TestRoleIndicators:
    def test_question_cells_marked_as_question(self, table_docx: bytes) -> None:
        """Non-empty cells in rows with answer targets get [question] hint."""
        result = extract_structure_compact(table_docx)
        lines = result.compact_text.split("\n")
        question_lines = [l for l in lines if "question" in l]
        assert len(question_lines) > 0

    def test_answer_cells_marked_as_answer(self, table_docx: bytes) -> None:
        """Empty cells in rows with questions get [answer] hint."""
        result = extract_structure_compact(table_docx)
        lines = result.compact_text.split("\n")
        answer_lines = [l for l in lines if "answer]" in l or "answer," in l]
        assert len(answer_lines) > 0

    def test_header_row_has_no_roles(self, table_docx: bytes) -> None:
        """Header rows (all non-empty) get no role indicators."""
        result = extract_structure_compact(table_docx)
        lines = result.compact_text.split("\n")
        # T1-R1-C1 is "Question" header — should NOT have question/answer role
        header_line = [l for l in lines if l.startswith("T1-R1-C1")]
        assert len(header_line) == 1
        assert "question" not in header_line[0]
        assert "answer" not in header_line[0]

    def test_question_and_answer_in_same_row(self, table_docx: bytes) -> None:
        """A data row should have both question and answer markers."""
        result = extract_structure_compact(table_docx)
        lines = result.compact_text.split("\n")
        # T1-R2-C1 is "What is your full legal name?" (question)
        # T1-R2-C2 is "" (empty answer target)
        r2c1 = [l for l in lines if l.startswith("T1-R2-C1")]
        r2c2 = [l for l in lines if l.startswith("T1-R2-C2")]
        assert len(r2c1) == 1
        assert len(r2c2) == 1
        assert "question" in r2c1[0]
        assert "answer" in r2c2[0]


# ── Layer 2: Suspicious-write warnings ───────────────────────────────────────


class TestSuspiciousWriteWarnings:
    def test_warning_when_targeting_question_cell(
        self, table_docx: bytes
    ) -> None:
        """Validating a question cell element ID triggers a WARNING."""
        # T1-R2-C1 has "What is your full legal name?" — not an answer target
        locations = [LocationSnippet(pair_id="q1", snippet="T1-R2-C1")]
        validated = validate_locations(table_docx, locations)

        assert validated[0].status == LocationStatus.MATCHED
        assert validated[0].context is not None
        assert "WARNING" in validated[0].context
        assert "question cell" in validated[0].context

    def test_warning_suggests_next_cell(self, table_docx: bytes) -> None:
        """Warning should suggest the next cell (T1-R2-C2) as alternative."""
        locations = [LocationSnippet(pair_id="q1", snippet="T1-R2-C1")]
        validated = validate_locations(table_docx, locations)

        assert "T1-R2-C2" in validated[0].context

    def test_no_warning_for_answer_cell(self, table_docx: bytes) -> None:
        """Validating an empty answer cell should NOT trigger a warning."""
        # T1-R2-C2 is empty — legitimate answer target
        locations = [LocationSnippet(pair_id="q1", snippet="T1-R2-C2")]
        validated = validate_locations(table_docx, locations)

        assert validated[0].status == LocationStatus.MATCHED
        assert "WARNING" not in (validated[0].context or "")

    def test_no_warning_for_paragraph(self, table_docx: bytes) -> None:
        """Paragraph element IDs (P1) should not trigger question warnings."""
        locations = [LocationSnippet(pair_id="p1", snippet="P1")]
        validated = validate_locations(table_docx, locations)

        assert validated[0].status == LocationStatus.MATCHED
        assert "WARNING" not in (validated[0].context or "")

    def test_warning_preserves_context(self, table_docx: bytes) -> None:
        """Warning should be prepended, not replace existing context text."""
        locations = [LocationSnippet(pair_id="q1", snippet="T1-R2-C1")]
        validated = validate_locations(table_docx, locations)

        # Should have both warning AND context text
        context = validated[0].context
        assert "WARNING" in context
        assert len(context) > len("WARNING")


# ── Layer 3: dry_run preview ────────────────────────────────────────────────


class TestDryRunPreview:
    def test_preview_returns_list(self, table_docx: bytes) -> None:
        """preview_answers returns a list of dicts."""
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
            answer_text="Acme Corp",
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        previews = preview_answers(table_docx, answers)
        assert isinstance(previews, list)
        assert len(previews) == 1

    def test_preview_shows_would_write(self, table_docx: bytes) -> None:
        """Preview should show what the answer would write."""
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
            answer_text="Acme Corp",
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        previews = preview_answers(table_docx, answers)
        assert previews[0]["would_write"] == "Acme Corp"
        assert previews[0]["pair_id"] == "q1"

    def test_preview_empty_cell_is_ok(self, table_docx: bytes) -> None:
        """Writing to an empty cell should have status 'ok'."""
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
            answer_text="Acme Corp",
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        previews = preview_answers(table_docx, answers)
        assert previews[0]["status"] == "ok"

    def test_preview_populated_cell_is_warning(self, table_docx: bytes) -> None:
        """Writing to a cell with existing text should have status 'warning'."""
        # T1-R2-C1 has question text
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[1]/w:p[1]",
            answer_text="Oops wrong cell",
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        previews = preview_answers(table_docx, answers)
        assert previews[0]["status"] == "warning"
        assert "message" in previews[0]

    def test_preview_bad_xpath_is_error(self, table_docx: bytes) -> None:
        """An XPath that doesn't match should return status 'error'."""
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[99]/w:tr[1]/w:tc[1]/w:p[1]",
            answer_text="Test",
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        previews = preview_answers(table_docx, answers)
        assert previews[0]["status"] == "error"

    def test_preview_does_not_modify_document(self, table_docx: bytes) -> None:
        """preview_answers must not change the original file bytes."""
        original = table_docx
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
            answer_text="Should not appear",
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        preview_answers(original, answers)

        # Re-extract and verify the answer cell is still empty
        result = extract_structure_compact(original)
        lines = result.compact_text.split("\n")
        r2c2 = [l for l in lines if l.startswith("T1-R2-C2")]
        assert "Should not appear" not in r2c2[0]

    def test_preview_multiple_answers(self, table_docx: bytes) -> None:
        """Preview handles multiple answers in a single call."""
        answers = [
            AnswerPayload(
                pair_id="q1",
                xpath="./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
                answer_text="Answer 1",
                mode=InsertionMode.REPLACE_CONTENT,
            ),
            AnswerPayload(
                pair_id="q2",
                xpath="./w:tbl[1]/w:tr[3]/w:tc[2]/w:p[1]",
                answer_text="Answer 2",
                mode=InsertionMode.REPLACE_CONTENT,
            ),
        ]
        previews = preview_answers(table_docx, answers)
        assert len(previews) == 2
        assert previews[0]["pair_id"] == "q1"
        assert previews[1]["pair_id"] == "q2"

    def test_preview_insertion_xml_describes_xml(self, table_docx: bytes) -> None:
        """When using insertion_xml, preview shows a descriptive string."""
        from src.xml_utils import NAMESPACES
        W = NAMESPACES["w"]
        answers = [AnswerPayload(
            pair_id="q1",
            xpath="./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
            insertion_xml=f'<w:r xmlns:w="{W}"><w:t>Test</w:t></w:r>',
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        previews = preview_answers(table_docx, answers)
        assert "pre-built XML" in previews[0]["would_write"]
