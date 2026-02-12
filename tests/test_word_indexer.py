"""Tests for the Word compact extraction / indexer module."""

from pathlib import Path

import pytest
from lxml import etree

from src.handlers.word_indexer import extract_structure_compact
from src.models import CompactStructureResponse
from src.xml_utils import NAMESPACES

FIXTURES = Path(__file__).parent / "fixtures"
INPUTS = Path(__file__).parent / "inputs"
W = NAMESPACES["w"]


@pytest.fixture
def table_docx() -> bytes:
    return (FIXTURES / "table_questionnaire.docx").read_bytes()


@pytest.fixture
def placeholder_docx() -> bytes:
    return (FIXTURES / "placeholder_form.docx").read_bytes()


@pytest.fixture
def vendor_docx() -> bytes:
    return (INPUTS / "Vendor_Questionnaire.docx").read_bytes()


# ── Return type and shape ───────────────────────────────────────────────────


class TestReturnShape:
    def test_returns_compact_structure_response(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert isinstance(result, CompactStructureResponse)

    def test_has_compact_text(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert isinstance(result.compact_text, str)
        assert len(result.compact_text) > 0

    def test_has_id_to_xpath_mapping(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert isinstance(result.id_to_xpath, dict)
        assert len(result.id_to_xpath) > 0

    def test_has_complex_elements_list(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert isinstance(result.complex_elements, list)


# ── Element ID scheme ───────────────────────────────────────────────────────


class TestElementIdScheme:
    def test_paragraph_ids_are_p_numbered(self, table_docx: bytes) -> None:
        """Top-level paragraphs get IDs like P1, P2, etc."""
        result = extract_structure_compact(table_docx)
        p_ids = [k for k in result.id_to_xpath if k.startswith("P")]
        assert len(p_ids) > 0
        # Should be sequential
        assert "P1" in result.id_to_xpath

    def test_table_cell_ids_are_t_r_c_numbered(self, table_docx: bytes) -> None:
        """Table cells get IDs like T1-R1-C1."""
        result = extract_structure_compact(table_docx)
        tc_ids = [k for k in result.id_to_xpath if k.startswith("T")]
        assert len(tc_ids) > 0
        assert "T1-R1-C1" in result.id_to_xpath

    def test_all_ids_appear_in_compact_text(self, table_docx: bytes) -> None:
        """Every ID in the mapping should appear in the compact text."""
        result = extract_structure_compact(table_docx)
        for element_id in result.id_to_xpath:
            assert element_id in result.compact_text, (
                f"ID {element_id} is in mapping but missing from compact_text"
            )


# ── Text content ────────────────────────────────────────────────────────────


class TestTextContent:
    def test_contains_question_text(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert "full legal name" in result.compact_text.lower()

    def test_contains_vendor_section_headers(self, vendor_docx: bytes) -> None:
        result = extract_structure_compact(vendor_docx)
        assert "General Company Information" in result.compact_text
        assert "Data Protection" in result.compact_text

    def test_contains_vendor_question_text(self, vendor_docx: bytes) -> None:
        result = extract_structure_compact(vendor_docx)
        assert "full legal company name" in result.compact_text.lower()


# ── Formatting hints ────────────────────────────────────────────────────────


class TestFormattingHints:
    def test_bold_is_detected(self, table_docx: bytes) -> None:
        """Header row cells are bold; should have [bold] hint."""
        result = extract_structure_compact(table_docx)
        # The header row has "Question" and "Answer" in bold
        lines = result.compact_text.split("\n")
        header_lines = [l for l in lines if "Question" in l or "Answer" in l]
        assert any("bold" in l for l in header_lines)


# ── Answer target detection ─────────────────────────────────────────────────


class TestAnswerTargets:
    def test_empty_cells_marked_as_targets(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert "answer target" in result.compact_text.lower()

    def test_empty_cells_marked_as_empty(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert "empty" in result.compact_text.lower()

    def test_placeholder_text_detected(self, placeholder_docx: bytes) -> None:
        result = extract_structure_compact(placeholder_docx)
        assert "placeholder" in result.compact_text.lower()


# ── XPath validity ──────────────────────────────────────────────────────────


class TestXPathValidity:
    def test_xpaths_resolve_to_elements(self, table_docx: bytes) -> None:
        """Every XPath in the mapping should resolve to a real element."""
        from src.handlers.word import _get_body_xml

        result = extract_structure_compact(table_docx)
        body_xml = _get_body_xml(table_docx)
        body = etree.fromstring(body_xml.encode("utf-8"))

        for element_id, xpath in result.id_to_xpath.items():
            matched = body.xpath(xpath, namespaces=NAMESPACES)
            assert len(matched) == 1, (
                f"XPath for {element_id} ({xpath}) matched "
                f"{len(matched)} elements, expected 1"
            )

    def test_vendor_xpaths_resolve(self, vendor_docx: bytes) -> None:
        """XPaths work on the larger vendor questionnaire too."""
        from src.handlers.word import _get_body_xml

        result = extract_structure_compact(vendor_docx)
        body_xml = _get_body_xml(vendor_docx)
        body = etree.fromstring(body_xml.encode("utf-8"))

        failed = []
        for element_id, xpath in result.id_to_xpath.items():
            matched = body.xpath(xpath, namespaces=NAMESPACES)
            if len(matched) != 1:
                failed.append(f"{element_id}: {xpath} -> {len(matched)} matches")

        assert not failed, f"Failed XPaths:\n" + "\n".join(failed)


# ── Compact size ────────────────────────────────────────────────────────────


class TestCompactSize:
    def test_much_smaller_than_raw_xml(self, vendor_docx: bytes) -> None:
        """Compact output should be much smaller than raw OOXML."""
        from src.handlers.word import extract_structure

        compact = extract_structure_compact(vendor_docx)
        raw = extract_structure(vendor_docx)

        compact_size = len(compact.compact_text)
        raw_size = len(raw.body_xml)

        # Compact should be at most 10% of raw size
        assert compact_size < raw_size * 0.1, (
            f"Compact ({compact_size}) should be much smaller "
            f"than raw ({raw_size})"
        )

    def test_compact_text_under_15kb(self, vendor_docx: bytes) -> None:
        """The compact text for the vendor questionnaire should be under 15KB."""
        result = extract_structure_compact(vendor_docx)
        assert len(result.compact_text) < 15_000


# ── Simple documents have no complex elements ──────────────────────────────


class TestComplexElements:
    def test_simple_table_has_no_complex_elements(self, table_docx: bytes) -> None:
        result = extract_structure_compact(table_docx)
        assert result.complex_elements == []

    def test_vendor_questionnaire_has_no_complex_elements(
        self, vendor_docx: bytes
    ) -> None:
        """The vendor questionnaire is simple tables — no complex elements."""
        result = extract_structure_compact(vendor_docx)
        assert result.complex_elements == []
