"""Tests for OOXML utility functions."""

from lxml import etree

from src.xml_formatting import (
    _parse_element_xml,
    extract_formatting_from_element,
)
from src.xml_utils import (
    NAMESPACES,
    build_run_xml,
    extract_formatting,
    find_snippet_in_body,
    is_well_formed_ooxml,
)

W = NAMESPACES["w"]


def _make_body(*children_xml: str) -> str:
    """Wrap child XML strings in a <w:body> element with namespace declarations."""
    inner = "".join(children_xml)
    return (
        f'<w:body xmlns:w="{W}" '
        f'xmlns:r="{NAMESPACES["r"]}">'
        f"{inner}</w:body>"
    )


def _make_paragraph(text: str, font: str = "Calibri", sz: str = "20") -> str:
    return (
        f"<w:p><w:r><w:rPr>"
        f'<w:rFonts w:ascii="{font}"/>'
        f'<w:sz w:val="{sz}"/>'
        f"</w:rPr>"
        f"<w:t>{text}</w:t></w:r></w:p>"
    )


class TestFindSnippetInBody:
    def test_finds_exact_match(self) -> None:
        para = _make_paragraph("Hello")
        body = _make_body(para)
        # The snippet as it would appear (with namespace prefix)
        snippet = (
            f'<w:p xmlns:w="{W}">'
            f'<w:r><w:rPr><w:rFonts w:ascii="Calibri"/>'
            f'<w:sz w:val="20"/></w:rPr>'
            f"<w:t>Hello</w:t></w:r></w:p>"
        )
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 1

    def test_no_match(self) -> None:
        para = _make_paragraph("Hello")
        body = _make_body(para)
        snippet = (
            f'<w:p xmlns:w="{W}">'
            f"<w:r><w:rPr/><w:t>Goodbye</w:t></w:r></w:p>"
        )
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 0

    def test_ambiguous_match(self) -> None:
        para = _make_paragraph("Same text")
        body = _make_body(para, para)
        snippet = (
            f'<w:p xmlns:w="{W}">'
            f'<w:r><w:rPr><w:rFonts w:ascii="Calibri"/>'
            f'<w:sz w:val="20"/></w:rPr>'
            f"<w:t>Same text</w:t></w:r></w:p>"
        )
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 2

    def test_snippet_without_namespace_decl(self) -> None:
        """Snippet that uses w: prefix but doesn't declare the namespace."""
        para = _make_paragraph("Test")
        body = _make_body(para)
        snippet = (
            "<w:p>"
            '<w:r><w:rPr><w:rFonts w:ascii="Calibri"/>'
            '<w:sz w:val="20"/></w:rPr>'
            "<w:t>Test</w:t></w:r></w:p>"
        )
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 1

    def test_matches_run_level(self) -> None:
        para = _make_paragraph("RunMatch")
        body = _make_body(para)
        snippet = (
            f'<w:r xmlns:w="{W}"><w:rPr>'
            f'<w:rFonts w:ascii="Calibri"/>'
            f'<w:sz w:val="20"/></w:rPr>'
            f"<w:t>RunMatch</w:t></w:r>"
        )
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 1

    def test_invalid_snippet_returns_empty(self) -> None:
        body = _make_body(_make_paragraph("X"))
        matches = find_snippet_in_body(body, "<not valid xml>>>")
        assert matches == []


class TestExtractFormatting:
    def test_extracts_font_and_size(self) -> None:
        xml = (
            f'<w:r xmlns:w="{W}"><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>'
            f'<w:sz w:val="24"/>'
            f"</w:rPr><w:t>text</w:t></w:r>"
        )
        fmt = extract_formatting(xml)
        assert fmt["font_ascii"] == "Arial"
        assert fmt["font_hAnsi"] == "Arial"
        assert fmt["sz"] == "24"

    def test_extracts_bold_italic(self) -> None:
        xml = (
            f'<w:r xmlns:w="{W}"><w:rPr>'
            f"<w:b/><w:i/>"
            f"</w:rPr><w:t>text</w:t></w:r>"
        )
        fmt = extract_formatting(xml)
        assert fmt["bold"] is True
        assert fmt["italic"] is True

    def test_extracts_from_paragraph(self) -> None:
        xml = (
            f'<w:p xmlns:w="{W}"><w:r><w:rPr>'
            f'<w:rFonts w:ascii="Calibri"/>'
            f'<w:sz w:val="22"/>'
            f"</w:rPr><w:t>text</w:t></w:r></w:p>"
        )
        fmt = extract_formatting(xml)
        assert fmt["font_ascii"] == "Calibri"
        assert fmt["sz"] == "22"

    def test_no_formatting_returns_empty(self) -> None:
        xml = f'<w:r xmlns:w="{W}"><w:t>plain</w:t></w:r>'
        fmt = extract_formatting(xml)
        assert fmt == {}

    def test_extracts_color(self) -> None:
        xml = (
            f'<w:r xmlns:w="{W}"><w:rPr>'
            f'<w:color w:val="FF0000"/>'
            f"</w:rPr><w:t>red</w:t></w:r>"
        )
        fmt = extract_formatting(xml)
        assert fmt["color"] == "FF0000"

    def test_snippet_without_namespace(self) -> None:
        xml = (
            "<w:r><w:rPr>"
            '<w:rFonts w:ascii="Calibri"/>'
            '<w:sz w:val="20"/>'
            "</w:rPr><w:t>text</w:t></w:r>"
        )
        fmt = extract_formatting(xml)
        assert fmt["font_ascii"] == "Calibri"


class TestBuildRunXml:
    def test_plain_text_no_formatting(self) -> None:
        xml = build_run_xml("Hello", {})
        elem = etree.fromstring(xml.encode("utf-8"))
        assert elem.tag == f"{{{W}}}r"
        t = elem.find(f"{{{W}}}t")
        assert t is not None
        assert t.text == "Hello"
        # No rPr when no formatting
        assert elem.find(f"{{{W}}}rPr") is None

    def test_with_formatting(self) -> None:
        fmt = {"font_ascii": "Arial", "sz": "24", "bold": True}
        xml = build_run_xml("Formatted", fmt)
        elem = etree.fromstring(xml.encode("utf-8"))
        rpr = elem.find(f"{{{W}}}rPr")
        assert rpr is not None
        assert rpr.find(f"{{{W}}}rFonts") is not None
        assert rpr.find(f"{{{W}}}rFonts").get(f"{{{W}}}ascii") == "Arial"
        assert rpr.find(f"{{{W}}}sz").get(f"{{{W}}}val") == "24"
        assert rpr.find(f"{{{W}}}b") is not None

    def test_preserves_leading_trailing_spaces(self) -> None:
        xml = build_run_xml(" spaced ", {})
        elem = etree.fromstring(xml.encode("utf-8"))
        t = elem.find(f"{{{W}}}t")
        assert t.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"

    def test_output_is_well_formed(self) -> None:
        fmt = {"font_ascii": "Calibri", "font_hAnsi": "Calibri", "sz": "22", "italic": True}
        xml = build_run_xml("test", fmt)
        # Should parse without error
        etree.fromstring(xml.encode("utf-8"))

    def test_newlines_become_br_elements(self) -> None:
        xml = build_run_xml("Line 1\nLine 2\nLine 3", {})
        elem = etree.fromstring(xml.encode("utf-8"))
        t_elems = elem.findall(f"{{{W}}}t")
        br_elems = elem.findall(f"{{{W}}}br")
        assert len(t_elems) == 3
        assert len(br_elems) == 2
        assert t_elems[0].text == "Line 1"
        assert t_elems[1].text == "Line 2"
        assert t_elems[2].text == "Line 3"

    def test_single_line_no_br(self) -> None:
        xml = build_run_xml("No newlines here", {})
        elem = etree.fromstring(xml.encode("utf-8"))
        assert len(elem.findall(f"{{{W}}}br")) == 0
        assert len(elem.findall(f"{{{W}}}t")) == 1


class TestIsWellFormedOoxml:
    def test_valid_run(self) -> None:
        xml = '<w:r><w:rPr><w:rFonts w:ascii="Calibri"/></w:rPr><w:t>hi</w:t></w:r>'
        valid, err = is_well_formed_ooxml(xml)
        assert valid is True
        assert err is None

    def test_valid_paragraph(self) -> None:
        xml = "<w:p><w:r><w:t>hello</w:t></w:r></w:p>"
        valid, err = is_well_formed_ooxml(xml)
        assert valid is True
        assert err is None

    def test_malformed_xml(self) -> None:
        xml = "<w:r><w:t>unclosed"
        valid, err = is_well_formed_ooxml(xml)
        assert valid is False
        assert "syntax error" in err.lower()

    def test_disallowed_element(self) -> None:
        xml = "<w:r><w:t>ok</w:t><w:script>bad</w:script></w:r>"
        valid, err = is_well_formed_ooxml(xml)
        assert valid is False
        assert "script" in err.lower()

    def test_empty_string(self) -> None:
        # Empty string wraps to just <_wrapper/>, no children to check
        valid, err = is_well_formed_ooxml("")
        assert valid is True


class TestExtractFormattingFromElement:
    """Tests for extract_formatting_from_element parity with the string-based version."""

    def test_matches_string_version(self) -> None:
        """Parsed element produces identical formatting dict as the string path."""
        xml_str = (
            f'<w:r xmlns:w="{W}"><w:rPr>'
            f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>'
            f'<w:sz w:val="24"/>'
            f"<w:b/>"
            f'<w:color w:val="0000FF"/>'
            f"</w:rPr><w:t>text</w:t></w:r>"
        )
        from_string = extract_formatting(xml_str)
        parsed_elem = _parse_element_xml(xml_str)
        from_element = extract_formatting_from_element(parsed_elem)
        assert from_string == from_element

    def test_empty_rpr(self) -> None:
        """Element with no <w:rPr> returns an empty dict."""
        xml_str = f'<w:r xmlns:w="{W}"><w:t>plain</w:t></w:r>'
        elem = _parse_element_xml(xml_str)
        fmt = extract_formatting_from_element(elem)
        assert fmt == {}

    def test_paragraph_with_run(self) -> None:
        """Extracts formatting from a run's rPr inside a <w:p> element."""
        xml_str = (
            f'<w:p xmlns:w="{W}"><w:r><w:rPr>'
            f'<w:rFonts w:ascii="Times New Roman"/>'
            f'<w:sz w:val="28"/>'
            f"<w:i/>"
            f"</w:rPr><w:t>styled</w:t></w:r></w:p>"
        )
        elem = _parse_element_xml(xml_str)
        fmt = extract_formatting_from_element(elem)
        assert fmt["font_ascii"] == "Times New Roman"
        assert fmt["sz"] == "28"
        assert fmt["italic"] is True

    def test_importable_from_xml_utils(self) -> None:
        """Confirm the function is importable from the barrel module."""
        from src.xml_utils import extract_formatting_from_element as barrel_fn

        assert callable(barrel_fn)
        # Also verify it's the same function object
        assert barrel_fn is extract_formatting_from_element
