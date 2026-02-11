"""OOXML utilities — snippet matching, XPath resolution, formatting inheritance,
well-formedness checks."""

from __future__ import annotations

from lxml import etree

# OOXML namespaces (canonical source)
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


def find_snippet_in_body(body_xml: str, snippet: str) -> list[str]:
    """Find all XPaths where *snippet* matches within the document body.

    Returns a list of XPath strings. Empty list means no match, more than one
    means ambiguous.
    """
    raise NotImplementedError


def extract_formatting(element_xml: str) -> dict:
    """Extract run-level formatting (font, size, bold, italic, etc.) from an
    OOXML element and return as a plain dict."""
    raise NotImplementedError


def build_run_xml(text: str, formatting: dict) -> str:
    """Build a <w:r> element with the given text and inherited formatting."""
    raise NotImplementedError


def is_well_formed_ooxml(xml_string: str) -> tuple[bool, str | None]:
    """Check that *xml_string* is well-formed XML using only legitimate OOXML
    elements and attributes.

    Returns (True, None) on success, (False, error_message) on failure.
    """
    raise NotImplementedError


def normalise_whitespace(xml_string: str) -> str:
    """Normalise whitespace in an XML string for comparison purposes."""
    raise NotImplementedError
