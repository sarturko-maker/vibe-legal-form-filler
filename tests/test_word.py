"""Tests for the Word (.docx) handler."""

from pathlib import Path

import pytest
from lxml import etree

from src.handlers.word import (
    build_insertion_xml,
    extract_structure,
    list_form_fields,
    validate_locations,
    write_answers,
)
from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    InsertionMode,
    LocationSnippet,
    LocationStatus,
)
from src.xml_utils import NAMESPACES

FIXTURES = Path(__file__).parent / "fixtures"
W = NAMESPACES["w"]


@pytest.fixture
def table_docx() -> bytes:
    return (FIXTURES / "table_questionnaire.docx").read_bytes()


@pytest.fixture
def placeholder_docx() -> bytes:
    return (FIXTURES / "placeholder_form.docx").read_bytes()


# ── extract_structure ────────────────────────────────────────────────────────


class TestExtractStructure:
    def test_returns_body_xml(self, table_docx: bytes) -> None:
        result = extract_structure(table_docx)
        assert result.body_xml is not None
        assert "<w:body" in result.body_xml

    def test_body_xml_is_parseable(self, table_docx: bytes) -> None:
        result = extract_structure(table_docx)
        root = etree.fromstring(result.body_xml.encode("utf-8"))
        assert root.tag == f"{{{W}}}body"

    def test_contains_table_elements(self, table_docx: bytes) -> None:
        result = extract_structure(table_docx)
        assert "<w:tbl" in result.body_xml or f"{{{W}}}tbl" in result.body_xml

    def test_contains_question_text(self, table_docx: bytes) -> None:
        result = extract_structure(table_docx)
        assert "full legal name" in result.body_xml

    def test_placeholder_form(self, placeholder_docx: bytes) -> None:
        result = extract_structure(placeholder_docx)
        assert result.body_xml is not None
        assert "Enter here" in result.body_xml or "Enter date" in result.body_xml

    def test_invalid_bytes_raises(self) -> None:
        with pytest.raises(Exception):
            extract_structure(b"not a docx file")


# ── validate_locations ───────────────────────────────────────────────────────


class TestValidateLocations:
    def test_matches_existing_paragraph(self, table_docx: bytes) -> None:
        """Extract a snippet from the actual document and validate it matches."""
        result = extract_structure(table_docx)
        body = etree.fromstring(result.body_xml.encode("utf-8"))

        # Find a specific table cell paragraph and use it as a snippet
        # Get the first table row's first cell paragraph
        first_tbl = body.find(".//w:tbl", NAMESPACES)
        assert first_tbl is not None
        # Get second row (first question row), second cell (answer cell)
        rows = first_tbl.findall("w:tr", NAMESPACES)
        assert len(rows) >= 2
        q_cell = rows[1].findall("w:tc", NAMESPACES)[0]
        q_para = q_cell.find("w:p", NAMESPACES)
        snippet_xml = etree.tostring(q_para, encoding="unicode")

        locations = [LocationSnippet(pair_id="q1", snippet=snippet_xml)]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 1
        assert validated[0].pair_id == "q1"
        assert validated[0].status == LocationStatus.MATCHED
        assert validated[0].xpath is not None

    def test_not_found(self, table_docx: bytes) -> None:
        fake_snippet = (
            f'<w:p xmlns:w="{W}">'
            f"<w:r><w:t>THIS TEXT DOES NOT EXIST IN THE DOCUMENT</w:t></w:r></w:p>"
        )
        locations = [LocationSnippet(pair_id="q_fake", snippet=fake_snippet)]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 1
        assert validated[0].status == LocationStatus.NOT_FOUND

    def test_multiple_locations(self, table_docx: bytes) -> None:
        """Validate multiple locations in one call."""
        result = extract_structure(table_docx)
        body = etree.fromstring(result.body_xml.encode("utf-8"))

        first_tbl = body.find(".//w:tbl", NAMESPACES)
        rows = first_tbl.findall("w:tr", NAMESPACES)

        snippets = []
        for i, row in enumerate(rows[1:3], start=1):  # rows 1 and 2
            q_cell = row.findall("w:tc", NAMESPACES)[0]
            q_para = q_cell.find("w:p", NAMESPACES)
            snippet_xml = etree.tostring(q_para, encoding="unicode")
            snippets.append(LocationSnippet(pair_id=f"q{i}", snippet=snippet_xml))

        validated = validate_locations(table_docx, snippets)
        assert len(validated) == 2
        assert all(v.status == LocationStatus.MATCHED for v in validated)

    def test_invalid_snippet_returns_not_found(self, table_docx: bytes) -> None:
        locations = [LocationSnippet(pair_id="bad", snippet="<not valid xml>>>")]
        validated = validate_locations(table_docx, locations)
        assert validated[0].status == LocationStatus.NOT_FOUND

    def test_element_id_table_cell_matched(self, table_docx: bytes) -> None:
        """Element IDs like T1-R1-C1 should resolve via the indexer mapping."""
        locations = [LocationSnippet(pair_id="q1", snippet="T1-R1-C1")]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 1
        assert validated[0].status == LocationStatus.MATCHED
        assert validated[0].xpath is not None
        assert "w:tbl[1]" in validated[0].xpath

    def test_element_id_paragraph_matched(self, table_docx: bytes) -> None:
        """Paragraph IDs like P1 should resolve via the indexer mapping."""
        locations = [LocationSnippet(pair_id="p1", snippet="P1")]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 1
        assert validated[0].status == LocationStatus.MATCHED
        assert validated[0].xpath is not None

    def test_element_id_not_found(self, table_docx: bytes) -> None:
        """A non-existent element ID should return NOT_FOUND."""
        locations = [LocationSnippet(pair_id="bad", snippet="T99-R99-C99")]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 1
        assert validated[0].status == LocationStatus.NOT_FOUND

    def test_element_id_multiple(self, table_docx: bytes) -> None:
        """Multiple element IDs validated in one call."""
        locations = [
            LocationSnippet(pair_id="q1", snippet="T1-R1-C1"),
            LocationSnippet(pair_id="q2", snippet="T1-R1-C2"),
            LocationSnippet(pair_id="q3", snippet="T1-R2-C1"),
        ]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 3
        assert all(v.status == LocationStatus.MATCHED for v in validated)
        # Each should have a distinct XPath
        xpaths = [v.xpath for v in validated]
        assert len(set(xpaths)) == 3

    def test_element_id_returns_context(self, table_docx: bytes) -> None:
        """Element ID validation should return context text from the element."""
        locations = [LocationSnippet(pair_id="q1", snippet="T1-R1-C1")]
        validated = validate_locations(table_docx, locations)

        assert validated[0].context is not None
        assert len(validated[0].context) > 0

    def test_mixed_element_ids_and_snippets(self, table_docx: bytes) -> None:
        """A call mixing element IDs and OOXML snippets should handle both."""
        result = extract_structure(table_docx)
        body = etree.fromstring(result.body_xml.encode("utf-8"))
        first_tbl = body.find(".//w:tbl", NAMESPACES)
        rows = first_tbl.findall("w:tr", NAMESPACES)
        q_cell = rows[1].findall("w:tc", NAMESPACES)[0]
        q_para = q_cell.find("w:p", NAMESPACES)
        snippet_xml = etree.tostring(q_para, encoding="unicode")

        locations = [
            LocationSnippet(pair_id="by_id", snippet="T1-R1-C1"),
            LocationSnippet(pair_id="by_snippet", snippet=snippet_xml),
        ]
        validated = validate_locations(table_docx, locations)

        assert len(validated) == 2
        assert validated[0].status == LocationStatus.MATCHED
        assert validated[1].status == LocationStatus.MATCHED


# ── build_insertion_xml ──────────────────────────────────────────────────────


class TestBuildInsertionXml:
    def test_plain_text_inherits_formatting(self) -> None:
        target_xml = (
            f'<w:p xmlns:w="{W}"><w:r><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>'
            f'<w:sz w:val="24"/>'
            f"</w:rPr><w:t>Question text</w:t></w:r></w:p>"
        )
        req = BuildInsertionXmlRequest(
            answer_text="My answer",
            target_context_xml=target_xml,
            answer_type=AnswerType.PLAIN_TEXT,
        )
        resp = build_insertion_xml(req)

        assert resp.valid is True
        assert resp.insertion_xml
        # Parse and verify formatting inheritance
        elem = etree.fromstring(resp.insertion_xml.encode("utf-8"))
        rpr = elem.find(f"{{{W}}}rPr")
        assert rpr is not None
        rfonts = rpr.find(f"{{{W}}}rFonts")
        assert rfonts is not None
        assert rfonts.get(f"{{{W}}}ascii") == "Arial"
        t = elem.find(f"{{{W}}}t")
        assert t.text == "My answer"

    def test_plain_text_no_formatting(self) -> None:
        target_xml = f'<w:p xmlns:w="{W}"><w:r><w:t>plain</w:t></w:r></w:p>'
        req = BuildInsertionXmlRequest(
            answer_text="Answer",
            target_context_xml=target_xml,
            answer_type=AnswerType.PLAIN_TEXT,
        )
        resp = build_insertion_xml(req)
        assert resp.valid is True
        elem = etree.fromstring(resp.insertion_xml.encode("utf-8"))
        assert elem.find(f"{{{W}}}rPr") is None

    def test_structured_valid_xml(self) -> None:
        structured = '<w:r><w:rPr><w:b/></w:rPr><w:t>Bold answer</w:t></w:r>'
        req = BuildInsertionXmlRequest(
            answer_text=structured,
            target_context_xml="",
            answer_type=AnswerType.STRUCTURED,
        )
        resp = build_insertion_xml(req)
        assert resp.valid is True
        assert resp.insertion_xml == structured

    def test_structured_invalid_xml(self) -> None:
        req = BuildInsertionXmlRequest(
            answer_text="<w:r><w:t>unclosed",
            target_context_xml="",
            answer_type=AnswerType.STRUCTURED,
        )
        resp = build_insertion_xml(req)
        assert resp.valid is False
        assert resp.error is not None

    def test_structured_disallowed_element(self) -> None:
        req = BuildInsertionXmlRequest(
            answer_text="<w:r><w:script>bad</w:script></w:r>",
            target_context_xml="",
            answer_type=AnswerType.STRUCTURED,
        )
        resp = build_insertion_xml(req)
        assert resp.valid is False


# ── write_answers ────────────────────────────────────────────────────────────


class TestWriteAnswers:
    def _get_answer_cell_xpath(self, file_bytes: bytes, row_index: int) -> str:
        """Helper: build XPath to the answer paragraph in a table row.

        Empty answer cells are structurally identical so snippet matching
        returns AMBIGUOUS. Instead we build the XPath directly.
        """
        result = extract_structure(file_bytes)
        body = etree.fromstring(result.body_xml.encode("utf-8"))
        # Build the XPath for: first table → row N → cell 2 → paragraph 1
        xpath = f"./w:tbl[1]/w:tr[{row_index + 1}]/w:tc[2]/w:p[1]"
        matched = body.xpath(xpath, namespaces=NAMESPACES)
        assert matched, f"XPath {xpath} did not match"
        return xpath

    def test_replace_content(self, table_docx: bytes) -> None:
        xpath = self._get_answer_cell_xpath(table_docx, 1)

        run_xml = (
            f'<w:r xmlns:w="{W}"><w:rPr>'
            f'<w:rFonts w:ascii="Calibri"/><w:sz w:val="20"/>'
            f"</w:rPr><w:t>Acme Corporation</w:t></w:r>"
        )
        answers = [AnswerPayload(
            pair_id="q1",
            xpath=xpath,
            insertion_xml=run_xml,
            mode=InsertionMode.REPLACE_CONTENT,
        )]

        result_bytes = write_answers(table_docx, answers)

        # Verify the answer was written
        result = extract_structure(result_bytes)
        assert "Acme Corporation" in result.body_xml

    def test_append(self, table_docx: bytes) -> None:
        xpath = self._get_answer_cell_xpath(table_docx, 1)

        run_xml = (
            f'<w:r xmlns:w="{W}"><w:t> (additional info)</w:t></w:r>'
        )
        answers = [AnswerPayload(
            pair_id="q1",
            xpath=xpath,
            insertion_xml=run_xml,
            mode=InsertionMode.APPEND,
        )]

        result_bytes = write_answers(table_docx, answers)
        result = extract_structure(result_bytes)
        assert "(additional info)" in result.body_xml

    def test_replace_placeholder(self, placeholder_docx: bytes) -> None:
        """Replace [Enter date] placeholder in the NDA form."""
        result = extract_structure(placeholder_docx)
        body = etree.fromstring(result.body_xml.encode("utf-8"))

        # Find the paragraph containing "[Enter date]"
        target_para = None
        for p in body.iter(f"{{{W}}}p"):
            for t in p.iter(f"{{{W}}}t"):
                if t.text and "[Enter date]" in t.text:
                    target_para = p
                    break
            if target_para is not None:
                break

        assert target_para is not None
        snippet_xml = etree.tostring(target_para, encoding="unicode")

        locations = [LocationSnippet(pair_id="date", snippet=snippet_xml)]
        validated = validate_locations(placeholder_docx, locations)
        assert validated[0].status == LocationStatus.MATCHED

        run_xml = f'<w:r xmlns:w="{W}"><w:t>January 15, 2026</w:t></w:r>'
        answers = [AnswerPayload(
            pair_id="date",
            xpath=validated[0].xpath,
            insertion_xml=run_xml,
            mode=InsertionMode.REPLACE_PLACEHOLDER,
        )]

        result_bytes = write_answers(placeholder_docx, answers)
        result2 = extract_structure(result_bytes)
        assert "January 15, 2026" in result2.body_xml
        assert "[Enter date]" not in result2.body_xml

    def test_multiple_answers(self, table_docx: bytes) -> None:
        """Write answers to multiple cells at once."""
        xpath1 = self._get_answer_cell_xpath(table_docx, 1)
        xpath2 = self._get_answer_cell_xpath(table_docx, 2)

        answers = [
            AnswerPayload(
                pair_id="q1",
                xpath=xpath1,
                insertion_xml=f'<w:r xmlns:w="{W}"><w:t>Acme Corp</w:t></w:r>',
                mode=InsertionMode.REPLACE_CONTENT,
            ),
            AnswerPayload(
                pair_id="q2",
                xpath=xpath2,
                insertion_xml=f'<w:r xmlns:w="{W}"><w:t>123 Main St</w:t></w:r>',
                mode=InsertionMode.REPLACE_CONTENT,
            ),
        ]

        result_bytes = write_answers(table_docx, answers)
        result = extract_structure(result_bytes)
        assert "Acme Corp" in result.body_xml
        assert "123 Main St" in result.body_xml

    def test_output_is_valid_docx(self, table_docx: bytes) -> None:
        """The output should be a valid .docx (ZIP) that we can re-extract."""
        xpath = self._get_answer_cell_xpath(table_docx, 1)
        answers = [AnswerPayload(
            pair_id="q1",
            xpath=xpath,
            insertion_xml=f'<w:r xmlns:w="{W}"><w:t>Test</w:t></w:r>',
            mode=InsertionMode.REPLACE_CONTENT,
        )]

        result_bytes = write_answers(table_docx, answers)
        # Should be able to extract structure from the result
        result = extract_structure(result_bytes)
        assert result.body_xml is not None

    def test_replace_content_preserves_tcPr(self, table_docx: bytes) -> None:
        """replace_content on a w:tc must preserve w:tcPr (cell properties)."""
        xpath = "./w:tbl[1]/w:tr[2]/w:tc[2]"
        run_xml = f'<w:r xmlns:w="{W}"><w:t>Acme Corporation</w:t></w:r>'
        answers = [AnswerPayload(
            pair_id="q1",
            xpath=xpath,
            insertion_xml=run_xml,
            mode=InsertionMode.REPLACE_CONTENT,
        )]

        result_bytes = write_answers(table_docx, answers)

        result = extract_structure(result_bytes)
        body = etree.fromstring(result.body_xml.encode("utf-8"))
        tc = body.xpath(xpath, namespaces=NAMESPACES)[0]
        assert tc.find(f"{{{W}}}tcPr") is not None, "w:tcPr was stripped"

    def test_replace_content_wraps_run_in_paragraph_for_tc(
        self, table_docx: bytes
    ) -> None:
        """replace_content on a w:tc must wrap w:r inside a w:p, not bare."""
        xpath = "./w:tbl[1]/w:tr[2]/w:tc[2]"
        run_xml = f'<w:r xmlns:w="{W}"><w:t>Acme Corporation</w:t></w:r>'
        answers = [AnswerPayload(
            pair_id="q1",
            xpath=xpath,
            insertion_xml=run_xml,
            mode=InsertionMode.REPLACE_CONTENT,
        )]

        result_bytes = write_answers(table_docx, answers)

        result = extract_structure(result_bytes)
        body = etree.fromstring(result.body_xml.encode("utf-8"))
        tc = body.xpath(xpath, namespaces=NAMESPACES)[0]

        # No bare w:r directly under w:tc
        bare_runs = [c for c in tc if c.tag == f"{{{W}}}r"]
        assert len(bare_runs) == 0, "w:r inserted directly under w:tc"

        # w:p should contain the answer text
        paras = tc.findall(f"{{{W}}}p")
        assert len(paras) >= 1, "No w:p found in cell"
        assert "Acme Corporation" in etree.tostring(paras[0], encoding="unicode")

    def test_invalid_xpath_raises(self, table_docx: bytes) -> None:
        answers = [AnswerPayload(
            pair_id="bad",
            xpath="/w:nonexistent/w:path",
            insertion_xml=f'<w:r xmlns:w="{W}"><w:t>X</w:t></w:r>',
            mode=InsertionMode.REPLACE_CONTENT,
        )]
        with pytest.raises(ValueError, match="did not match"):
            write_answers(table_docx, answers)


# ── list_form_fields ─────────────────────────────────────────────────────────


class TestListFormFields:
    def test_detects_empty_table_cells(self, table_docx: bytes) -> None:
        fields = list_form_fields(table_docx)
        table_fields = [f for f in fields if f.field_type == "table_cell"]
        # Should find the 6 empty answer cells in table 1 + 3 in table 2
        assert len(table_fields) >= 6

    def test_detects_placeholder_text(self, placeholder_docx: bytes) -> None:
        fields = list_form_fields(placeholder_docx)
        placeholder_fields = [f for f in fields if f.field_type == "placeholder"]
        # Should find [Enter date], [Enter here] x4, [Enter number],
        # [Enter jurisdiction], ___ x3
        assert len(placeholder_fields) >= 5

    def test_field_labels_contain_text(self, table_docx: bytes) -> None:
        fields = list_form_fields(table_docx)
        table_fields = [f for f in fields if f.field_type == "table_cell"]
        labels = [f.label for f in table_fields]
        assert any("legal name" in l.lower() for l in labels)

    def test_placeholder_fields_have_current_value(self, placeholder_docx: bytes) -> None:
        fields = list_form_fields(placeholder_docx)
        placeholder_fields = [f for f in fields if f.field_type == "placeholder"]
        for f in placeholder_fields:
            assert f.current_value is not None


# ── Full pipeline test ───────────────────────────────────────────────────────


class TestFullPipeline:
    def test_extract_validate_build_write(self, table_docx: bytes) -> None:
        """Full pipeline: extract → validate → build → write."""
        # 1. Extract structure
        structure = extract_structure(table_docx)
        body = etree.fromstring(structure.body_xml.encode("utf-8"))

        # 2. Find the question cell for the first question (unique text)
        first_tbl = body.find(".//w:tbl", NAMESPACES)
        rows = first_tbl.findall("w:tr", NAMESPACES)
        q_cell = rows[1].findall("w:tc", NAMESPACES)[0]
        q_para = q_cell.find("w:p", NAMESPACES)
        snippet = etree.tostring(q_para, encoding="unicode")

        # 3. Validate location of the question paragraph
        validated = validate_locations(
            table_docx,
            [LocationSnippet(pair_id="q1", snippet=snippet)],
        )
        assert validated[0].status == LocationStatus.MATCHED

        # 4. Build insertion XML (inherit formatting from the question cell)
        context_xml = etree.tostring(q_para, encoding="unicode")
        build_resp = build_insertion_xml(BuildInsertionXmlRequest(
            answer_text="Acme Corporation Ltd.",
            target_context_xml=context_xml,
            answer_type=AnswerType.PLAIN_TEXT,
        ))
        assert build_resp.valid

        # 5. Write the answer to the corresponding answer cell
        # (In practice, the agent maps question XPaths to answer cell XPaths;
        #  here we use the known table structure directly.)
        answer_xpath = "./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]"
        result_bytes = write_answers(table_docx, [AnswerPayload(
            pair_id="q1",
            xpath=answer_xpath,
            insertion_xml=build_resp.insertion_xml,
            mode=InsertionMode.REPLACE_CONTENT,
        )])

        # 6. Verify
        result = extract_structure(result_bytes)
        assert "Acme Corporation Ltd." in result.body_xml
