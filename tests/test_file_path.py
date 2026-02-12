"""Tests for the file_path parameter on MCP tools.

Verifies that resolve_file_input() correctly handles file_path, file_bytes_b64,
type inference from extensions, and error cases. Also tests that MCP tool
functions work end-to-end when given a file_path instead of base64 bytes.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.models import FileType
from src.validators import resolve_file_input

FIXTURES = Path(__file__).parent / "fixtures"
INPUTS = Path(__file__).parent / "inputs"


# ── resolve_file_input unit tests ─────────────────────────────────────────────


class TestResolveFromPath:
    """Tests for the file_path code path."""

    def test_reads_docx_and_infers_word(self) -> None:
        raw, ft = resolve_file_input(None, None, str(FIXTURES / "table_questionnaire.docx"))
        assert ft == FileType.WORD
        assert raw[:2] == b"PK"
        assert len(raw) > 100

    def test_explicit_file_type_overrides_extension(self) -> None:
        """When both file_path and file_type are provided, file_type wins."""
        # .docx is a ZIP, and so is .xlsx — both start with PK.
        # Passing file_type=excel should return EXCEL even for a .docx file.
        raw, ft = resolve_file_input(None, "excel", str(FIXTURES / "table_questionnaire.docx"))
        assert ft == FileType.EXCEL

    def test_unknown_extension_raises(self, tmp_path: Path) -> None:
        fake = tmp_path / "data.xyz"
        fake.write_bytes(b"PK fake content")
        with pytest.raises(ValueError, match="Cannot infer file_type"):
            resolve_file_input(None, None, str(fake))

    def test_missing_file_raises(self) -> None:
        with pytest.raises(ValueError, match="File not found"):
            resolve_file_input(None, None, "/nonexistent/path.docx")

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.docx"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="file_bytes is empty"):
            resolve_file_input(None, None, str(empty))

    def test_bad_magic_bytes_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.docx"
        bad.write_bytes(b"NOT A ZIP")
        with pytest.raises(ValueError, match="does not appear to be a valid"):
            resolve_file_input(None, None, str(bad))


class TestResolveFromBase64:
    """Tests for the file_bytes_b64 code path (existing behavior)."""

    def test_decodes_base64_with_explicit_type(self) -> None:
        original = (FIXTURES / "table_questionnaire.docx").read_bytes()
        b64 = base64.b64encode(original).decode()
        raw, ft = resolve_file_input(b64, "word", None)
        assert ft == FileType.WORD
        assert raw == original

    def test_missing_file_type_raises(self) -> None:
        b64 = base64.b64encode(b"PK fake").decode()
        with pytest.raises(ValueError, match="file_type is required"):
            resolve_file_input(b64, None, None)


class TestResolveNeitherProvided:
    """Tests for the error case when no input is given."""

    def test_raises_when_both_empty(self) -> None:
        with pytest.raises(ValueError, match="Provide either"):
            resolve_file_input(None, None, None)

    def test_raises_when_empty_strings(self) -> None:
        """Empty strings are treated as None by the server layer."""
        with pytest.raises(ValueError, match="Provide either"):
            resolve_file_input(None, None, None)


class TestFilePathPrecedence:
    """file_path takes precedence when both are provided."""

    def test_file_path_wins_over_base64(self) -> None:
        real_path = str(FIXTURES / "table_questionnaire.docx")
        garbage_b64 = base64.b64encode(b"not real data").decode()
        # file_path is valid, so it should succeed despite garbage b64
        raw, ft = resolve_file_input(garbage_b64, None, real_path)
        assert ft == FileType.WORD
        assert raw[:2] == b"PK"


# ── MCP tool integration tests ───────────────────────────────────────────────


class TestExtractStructureCompactWithPath:
    """extract_structure_compact works with file_path."""

    def test_returns_compact_text(self) -> None:
        from src.server import extract_structure_compact

        result = extract_structure_compact(file_path=str(FIXTURES / "table_questionnaire.docx"))
        assert "compact_text" in result
        assert "id_to_xpath" in result
        assert len(result["compact_text"]) > 0

    def test_vendor_questionnaire(self) -> None:
        from src.server import extract_structure_compact

        result = extract_structure_compact(file_path=str(INPUTS / "Vendor_Questionnaire.docx"))
        assert "compact_text" in result
        assert "T1" in result["compact_text"]


class TestExtractStructureWithPath:
    """extract_structure works with file_path."""

    def test_returns_body_xml(self) -> None:
        from src.server import extract_structure

        result = extract_structure(file_path=str(FIXTURES / "table_questionnaire.docx"))
        assert "body_xml" in result
        assert "<w:body" in result["body_xml"]


class TestListFormFieldsWithPath:
    """list_form_fields works with file_path."""

    def test_returns_fields(self) -> None:
        from src.server import list_form_fields

        result = list_form_fields(file_path=str(FIXTURES / "table_questionnaire.docx"))
        assert "fields" in result
        assert len(result["fields"]) > 0


class TestWriteAnswersOutputPath:
    """write_answers writes to disk when output_file_path is provided."""

    def _get_answer_xpath(self, docx_path: str) -> str:
        """Use extract_structure_compact to find a valid answer cell XPath."""
        from src.server import extract_structure_compact

        result = extract_structure_compact(file_path=docx_path)
        id_to_xpath = result["id_to_xpath"]
        # Find first empty answer target — look for row 2 cell 2
        for eid, xpath in id_to_xpath.items():
            if "tc[2]" in xpath and "tr[2]" in xpath:
                return xpath
        # Fallback: use any cell xpath
        return next(iter(id_to_xpath.values()))

    def test_writes_to_disk(self, tmp_path: Path) -> None:
        from src.server import extract_structure, write_answers

        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        docx_path = str(FIXTURES / "table_questionnaire.docx")
        xpath = self._get_answer_xpath(docx_path)

        insertion_xml = f'<w:r xmlns:w="{W}"><w:t>Test Answer</w:t></w:r>'
        answers = [
            {
                "pair_id": "q1",
                "xpath": xpath,
                "insertion_xml": insertion_xml,
                "mode": "replace_content",
            }
        ]

        out = tmp_path / "filled.docx"
        result = write_answers(
            answers=answers,
            file_path=docx_path,
            output_file_path=str(out),
        )

        assert result["file_path"] == str(out)
        assert out.exists()
        assert out.stat().st_size > 100

        # Verify the output is a valid docx by extracting from it
        result2 = extract_structure(file_path=str(out))
        assert "Test Answer" in result2["body_xml"]

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        from src.server import write_answers

        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        docx_path = str(FIXTURES / "table_questionnaire.docx")
        xpath = self._get_answer_xpath(docx_path)

        insertion_xml = f'<w:r xmlns:w="{W}"><w:t>X</w:t></w:r>'
        answers = [
            {"pair_id": "q1", "xpath": xpath, "insertion_xml": insertion_xml, "mode": "replace_content"}
        ]

        nested = tmp_path / "a" / "b" / "c" / "out.docx"
        result = write_answers(answers=answers, file_path=docx_path, output_file_path=str(nested))
        assert nested.exists()
        assert result["file_path"] == str(nested)
