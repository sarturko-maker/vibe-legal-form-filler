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
