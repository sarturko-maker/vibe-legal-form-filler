"""Tests for Phase 9 ergonomics and tolerance improvements.

Covers: file_path echo in extract_structure_compact, improved write_answers
error messages, SKIP sentinel detection, and response summary counts.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.server import (
    extract_structure_compact,
    write_answers,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── ERG-01: file_path echo ───────────────────────────────────────────────────


class TestExtractCompactFilePathEcho:
    """extract_structure_compact echoes file_path in response when provided."""

    @pytest.fixture
    def docx_path(self) -> str:
        return str(FIXTURES / "table_questionnaire.docx")

    @pytest.fixture
    def xlsx_path(self) -> str:
        return str(FIXTURES / "vendor_assessment.xlsx")

    def test_extract_compact_echoes_file_path(self, docx_path: str) -> None:
        """Response includes file_path matching the input path (Word)."""
        result = extract_structure_compact(file_path=docx_path)
        assert "file_path" in result
        assert result["file_path"] == docx_path

    def test_extract_compact_no_file_path_for_b64(self, docx_path: str) -> None:
        """Response omits file_path when agent uses file_bytes_b64."""
        raw = Path(docx_path).read_bytes()
        b64 = base64.b64encode(raw).decode()
        result = extract_structure_compact(
            file_bytes_b64=b64, file_type="word"
        )
        assert "file_path" not in result

    def test_extract_compact_echoes_file_path_excel(
        self, xlsx_path: str
    ) -> None:
        """Response includes file_path matching the input path (Excel)."""
        result = extract_structure_compact(file_path=xlsx_path)
        assert "file_path" in result
        assert result["file_path"] == xlsx_path


# ── ERG-02: write_answers error message ──────────────────────────────────────


class TestWriteAnswersErrorMessage:
    """write_answers error for missing file mentions extract_structure_compact."""

    def test_write_answers_missing_file_error_mentions_extract(self) -> None:
        """Error message says 'Missing file_path' and names the tool."""
        with pytest.raises(ValueError, match="Missing file_path") as exc_info:
            write_answers(answers=[{"pair_id": "T1-R2-C2", "answer_text": "X"}])
        assert "extract_structure_compact" in str(exc_info.value)

    def test_other_tool_error_does_not_mention_extract(self) -> None:
        """extract_structure_compact error does NOT show the write_answers hint."""
        with pytest.raises(ValueError) as exc_info:
            extract_structure_compact()
        msg = str(exc_info.value)
        assert "Missing file_path" not in msg
        assert "extract_structure_compact error" in msg


# ── TOL-01: SKIP detection ──────────────────────────────────────────────────


class TestSkipConvention:
    """answer_text='SKIP' causes no write and status='skipped' in response."""

    @pytest.fixture
    def docx_path(self) -> str:
        return str(FIXTURES / "table_questionnaire.docx")

    def test_skip_answer_not_written(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """SKIP answer is not written; non-SKIP answers are written."""
        out = tmp_path / "skip_test.docx"
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Acme Corp"},
                {"pair_id": "T1-R3-C2", "answer_text": "SKIP"},
                {"pair_id": "T1-R4-C2", "answer_text": "Jane CEO"},
            ],
            file_path=docx_path,
            output_file_path=str(out),
        )
        # Verify the SKIP cell is still empty
        compact = extract_structure_compact(file_path=str(out))
        for line in compact["compact_text"].split("\n"):
            if line.startswith("T1-R3-C2:"):
                assert "empty" in line.lower() or '""' in line
                break
        else:
            pytest.fail("T1-R3-C2 not found in compact output")
        # Verify non-SKIP answers were written
        for line in compact["compact_text"].split("\n"):
            if line.startswith("T1-R2-C2:"):
                assert "Acme Corp" in line
                break

    def test_skip_case_insensitive(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Lowercase 'skip' is also recognized as SKIP."""
        out = tmp_path / "skip_lower.docx"
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "skip"},
            ],
            file_path=docx_path,
            output_file_path=str(out),
        )
        assert result["summary"]["skipped"] == 1
        assert result["summary"]["written"] == 0

    def test_all_skip_returns_original(self, docx_path: str) -> None:
        """All-SKIP answers return original file bytes unchanged."""
        original_bytes = Path(docx_path).read_bytes()
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "SKIP"},
                {"pair_id": "T1-R3-C2", "answer_text": "SKIP"},
            ],
            file_path=docx_path,
        )
        returned_bytes = base64.b64decode(result["file_bytes_b64"])
        assert returned_bytes == original_bytes


# ── TOL-02: summary counts ──────────────────────────────────────────────────


class TestWriteAnswersSummary:
    """write_answers response always includes summary with counts."""

    @pytest.fixture
    def docx_path(self) -> str:
        return str(FIXTURES / "table_questionnaire.docx")

    def test_summary_always_present(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Summary present with written=2, skipped=0 when no SKIP answers."""
        out = tmp_path / "summary_test.docx"
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Acme Corp"},
                {"pair_id": "T1-R3-C2", "answer_text": "123 Main St"},
            ],
            file_path=docx_path,
            output_file_path=str(out),
        )
        assert "summary" in result
        assert result["summary"]["written"] == 2
        assert result["summary"]["skipped"] == 0

    def test_summary_with_skips(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Summary reflects correct counts when some answers are SKIP."""
        out = tmp_path / "summary_skip.docx"
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Acme Corp"},
                {"pair_id": "T1-R3-C2", "answer_text": "123 Main St"},
                {"pair_id": "T1-R4-C2", "answer_text": "SKIP"},
            ],
            file_path=docx_path,
            output_file_path=str(out),
        )
        assert result["summary"]["written"] == 2
        assert result["summary"]["skipped"] == 1

    def test_dry_run_shows_skip_status(self, docx_path: str) -> None:
        """dry_run preview includes SKIP answer with status='skipped'."""
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Acme Corp"},
                {"pair_id": "T1-R3-C2", "answer_text": "SKIP"},
            ],
            file_path=docx_path,
            dry_run=True,
        )
        assert "preview" in result
        assert "summary" in result
        assert result["summary"]["written"] == 1
        assert result["summary"]["skipped"] == 1
        # Find the skipped entry in the preview
        skip_entries = [
            p for p in result["preview"] if p.get("status") == "skipped"
        ]
        assert len(skip_entries) == 1
        assert skip_entries[0]["pair_id"] == "T1-R3-C2"
        assert "SKIP" in skip_entries[0]["message"]
