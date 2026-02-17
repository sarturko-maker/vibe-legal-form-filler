"""E2E tests for pair_id-only write_answers (resolution pipeline).

Tests that agents can call write_answers with just pair_id + answer_text
(no xpath, no mode) and the server resolves everything automatically.
Also tests cross-check warnings and backward compatibility.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import openpyxl
import pytest

from src.server import (
    extract_structure_compact,
    verify_output,
    write_answers,
)

FIXTURES = Path(__file__).parent / "fixtures"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class TestPairIdOnlyWrite:
    """Tests for pair_id-only write_answers (no xpath, no mode)."""

    @pytest.fixture
    def docx_path(self) -> str:
        return str(FIXTURES / "table_questionnaire.docx")

    @pytest.fixture
    def xlsx_path(self) -> str:
        return str(FIXTURES / "vendor_assessment.xlsx")

    def test_write_answers_pair_id_only_word(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Call write_answers with only pair_id and answer_text for Word."""
        out = tmp_path / "pair_id_only.docx"
        result = write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Acme Corp"},
            ],
            file_path=docx_path,
            output_file_path=str(out),
        )
        assert out.exists()

        # Verify the answer was written by re-extracting
        compact = extract_structure_compact(file_path=str(out))
        # Find the line for T1-R2-C2
        for line in compact["compact_text"].split("\n"):
            if line.startswith("T1-R2-C2:"):
                assert "Acme Corp" in line
                break
        else:
            pytest.fail("T1-R2-C2 not found in compact output")

    def test_write_answers_pair_id_only_defaults_mode(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Mode defaults to replace_content (existing content is replaced)."""
        # First write something to the cell
        step1 = tmp_path / "step1.docx"
        write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Original Text"},
            ],
            file_path=docx_path,
            output_file_path=str(step1),
        )

        # Now overwrite with pair_id-only (should replace, not append)
        step2 = tmp_path / "step2.docx"
        write_answers(
            answers=[
                {"pair_id": "T1-R2-C2", "answer_text": "Replacement"},
            ],
            file_path=str(step1),
            output_file_path=str(step2),
        )

        # Verify replacement happened (Original Text should be gone)
        with zipfile.ZipFile(str(step2)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "Replacement" in doc_xml
        assert "Original Text" not in doc_xml

    def test_write_answers_cross_check_warning(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Cross-check warns when agent xpath differs from resolved xpath."""
        # Get the real xpath for T1-R2-C2
        compact = extract_structure_compact(file_path=docx_path)
        real_xpath = compact["id_to_xpath"]["T1-R2-C2"]

        # Send a deliberately wrong xpath with the correct pair_id
        wrong_xpath = "./w:tbl[99]/w:tr[99]/w:tc[99]"
        out = tmp_path / "cross_check.docx"
        result = write_answers(
            answers=[{
                "pair_id": "T1-R2-C2",
                "xpath": wrong_xpath,
                "answer_text": "Cross Check Corp",
            }],
            file_path=docx_path,
            output_file_path=str(out),
        )

        # Verify warnings are present
        assert "warnings" in result
        assert len(result["warnings"]) > 0
        assert "T1-R2-C2" in result["warnings"][0]
        assert "differs" in result["warnings"][0]

        # Verify the answer was written at the CORRECT location
        # (resolved from pair_id, not the wrong xpath)
        compact_out = extract_structure_compact(file_path=str(out))
        for line in compact_out["compact_text"].split("\n"):
            if line.startswith("T1-R2-C2:"):
                assert "Cross Check Corp" in line
                break
        else:
            pytest.fail("Answer not found at correct location")

    def test_write_answers_pair_id_not_found(
        self, docx_path: str, tmp_path: Path
    ) -> None:
        """Unresolvable pair_id raises ValueError with clear message."""
        with pytest.raises(ValueError, match="could not be resolved"):
            write_answers(
                answers=[{
                    "pair_id": "T99-R99-C99",
                    "answer_text": "Ghost Corp",
                }],
                file_path=docx_path,
            )

    def test_write_answers_insertion_xml_still_requires_xpath(
        self, docx_path: str
    ) -> None:
        """insertion_xml path still requires explicit xpath and mode."""
        with pytest.raises(ValueError, match="insertion_xml requires explicit xpath"):
            write_answers(
                answers=[{
                    "pair_id": "T1-R2-C2",
                    "insertion_xml": f'<w:r xmlns:w="{W}"><w:t>X</w:t></w:r>',
                }],
                file_path=docx_path,
            )

    def test_write_answers_pair_id_only_excel(
        self, xlsx_path: str, tmp_path: Path
    ) -> None:
        """Call write_answers with only pair_id and answer_text for Excel."""
        out = tmp_path / "pair_id_only.xlsx"
        result = write_answers(
            answers=[
                {"pair_id": "S1-R2-C2", "answer_text": "Excel Corp"},
            ],
            file_path=xlsx_path,
            output_file_path=str(out),
        )
        assert out.exists()

        # Verify the answer with openpyxl
        wb = openpyxl.load_workbook(str(out))
        ws = wb.worksheets[0]
        # S1-R2-C2 = sheet 1, row 2, col 2
        cell_value = ws.cell(row=2, column=2).value
        wb.close()
        assert cell_value == "Excel Corp", f"Expected 'Excel Corp', got '{cell_value}'"
