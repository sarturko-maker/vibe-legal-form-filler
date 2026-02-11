"""OOXML utilities — snippet matching, XPath resolution, formatting inheritance,
well-formedness checks."""

from __future__ import annotations

import re

from lxml import etree

# OOXML namespaces (canonical source)
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

# Reverse mapping: full URI → prefix
_URI_TO_PREFIX = {v: k for k, v in NAMESPACES.items()}

# Allowed OOXML element local names (wordprocessingml). Not exhaustive but covers
# the elements that legitimately appear in run/paragraph-level insertion XML.
_ALLOWED_OOXML_ELEMENTS = {
    # Paragraph-level
    "p", "pPr", "pStyle", "jc", "spacing", "ind", "numPr", "ilvl", "numId",
    "pBdr", "tabs", "tab", "rPr",
    # Run-level
    "r", "rPr", "rFonts", "sz", "szCs", "b", "bCs", "i", "iCs", "u",
    "strike", "dstrike", "color", "highlight", "vertAlign", "lang",
    "t", "br", "cr", "tab", "sym",
    # Run property extras
    "caps", "smallCaps", "vanish", "spacing", "kern", "position",
    "shd", "effect", "em",
    # Table-level (for context)
    "tbl", "tblPr", "tblGrid", "gridCol", "tr", "trPr", "tc", "tcPr",
    "tblW", "tblBorders", "tblStyle", "tblLook",
    "tcW", "tcBorders", "vAlign", "gridSpan", "vMerge",
    # Bookmarks / content controls
    "bookmarkStart", "bookmarkEnd", "sdt", "sdtPr", "sdtContent",
    # Drawing (allowed but not deeply validated)
    "drawing",
}


def normalise_whitespace(xml_string: str) -> str:
    """Normalise whitespace in an XML string for comparison purposes.

    Collapses runs of whitespace between tags, strips leading/trailing whitespace,
    and normalises whitespace within text nodes.
    """
    # Remove whitespace between tags
    result = re.sub(r">\s+<", "><", xml_string.strip())
    # Collapse whitespace runs inside text content
    result = re.sub(r"\s+", " ", result)
    return result


def _build_xpath(element: etree._Element, root: etree._Element) -> str:
    """Build an XPath expression from *root* down to *element*."""
    parts: list[str] = []
    current = element
    while current is not root and current is not None:
        tag = current.tag
        # Convert Clark notation {uri}local to prefix:local
        if tag.startswith("{"):
            uri, local = tag[1:].split("}", 1)
            prefix = _URI_TO_PREFIX.get(uri)
            if prefix:
                qname = f"{prefix}:{local}"
            else:
                qname = local
        else:
            qname = tag

        # Count preceding siblings with the same tag for positional predicate
        parent = current.getparent()
        if parent is not None:
            same_tag_siblings = [c for c in parent if c.tag == current.tag]
            if len(same_tag_siblings) > 1:
                pos = same_tag_siblings.index(current) + 1
                qname = f"{qname}[{pos}]"

        parts.append(qname)
        current = parent

    parts.reverse()
    return "./" + "/".join(parts)


def _normalised_text_content(element: etree._Element) -> str:
    """Extract all text content from an element, normalised."""
    texts = element.itertext()
    return " ".join("".join(texts).split())


def _elements_text_match(a: etree._Element, b: etree._Element) -> bool:
    """Check if two elements have equivalent text content (normalised)."""
    return _normalised_text_content(a) == _normalised_text_content(b)


def _elements_structurally_equal(a: etree._Element, b: etree._Element) -> bool:
    """Recursively compare two lxml elements for structural equality.

    Ignores namespace declarations (which vary depending on tree context)
    and normalises whitespace in text content.
    """
    # Tags must match (Clark notation, e.g. {uri}local)
    if a.tag != b.tag:
        return False

    # Attributes must match (already in Clark notation, namespace-aware)
    if dict(a.attrib) != dict(b.attrib):
        return False

    # Text content (normalised)
    a_text = (a.text or "").strip()
    b_text = (b.text or "").strip()
    if a_text != b_text:
        return False

    # Tail text
    a_tail = (a.tail or "").strip()
    b_tail = (b.tail or "").strip()
    if a_tail != b_tail:
        return False

    # Children count and recursive comparison
    a_children = list(a)
    b_children = list(b)
    if len(a_children) != len(b_children):
        return False

    return all(
        _elements_structurally_equal(ac, bc)
        for ac, bc in zip(a_children, b_children)
    )


def _parse_snippet(snippet: str) -> etree._Element | None:
    """Parse an OOXML snippet, auto-wrapping with namespace decls if needed."""
    try:
        return etree.fromstring(snippet.encode("utf-8"))
    except etree.XMLSyntaxError:
        wrapper = (
            f'<_wrapper xmlns:w="{NAMESPACES["w"]}" '
            f'xmlns:r="{NAMESPACES["r"]}" '
            f'xmlns:wp="{NAMESPACES["wp"]}">'
            f"{snippet}</_wrapper>"
        )
        try:
            wrapper_elem = etree.fromstring(wrapper.encode("utf-8"))
            return wrapper_elem[0]
        except etree.XMLSyntaxError:
            return None


def find_snippet_in_body(body_xml: str, snippet: str) -> list[str]:
    """Find all XPaths where *snippet* matches within the document body.

    The snippet is parsed as XML and then compared structurally against every
    element of the same type in the body tree. Comparison ignores namespace
    declarations (which vary by tree context) and normalises whitespace.

    Returns a list of XPath strings. Empty list means no match, more than one
    means ambiguous.
    """
    body_root = etree.fromstring(body_xml.encode("utf-8"))

    snippet_elem = _parse_snippet(snippet)
    if snippet_elem is None:
        return []

    snippet_tag = snippet_elem.tag

    matches: list[str] = []
    for elem in body_root.iter(snippet_tag):
        if _elements_structurally_equal(elem, snippet_elem):
            xpath = _build_xpath(elem, body_root)
            matches.append(xpath)

    return matches


def extract_formatting(element_xml: str) -> dict:
    """Extract run-level formatting (font, size, bold, italic, etc.) from an
    OOXML element and return as a plain dict.

    Looks for <w:rPr> within the element and extracts known formatting
    properties. If the element is a paragraph (<w:p>), looks at the first
    run's properties or the paragraph-level rPr.
    """
    try:
        elem = etree.fromstring(element_xml.encode("utf-8"))
    except etree.XMLSyntaxError:
        wrapper = (
            f'<_wrapper xmlns:w="{NAMESPACES["w"]}" '
            f'xmlns:r="{NAMESPACES["r"]}">'
            f"{element_xml}</_wrapper>"
        )
        elem = etree.fromstring(wrapper.encode("utf-8"))[0]

    fmt: dict = {}

    # Look for rPr in multiple places
    rpr = None

    # Direct child rPr (if element is a run)
    rpr = elem.find("w:rPr", NAMESPACES)

    # If element is a paragraph, look at first run's rPr
    if rpr is None:
        first_run = elem.find(".//w:r", NAMESPACES)
        if first_run is not None:
            rpr = first_run.find("w:rPr", NAMESPACES)

    # Paragraph-level rPr
    if rpr is None:
        ppr = elem.find("w:pPr", NAMESPACES)
        if ppr is not None:
            rpr = ppr.find("w:rPr", NAMESPACES)

    if rpr is None:
        return fmt

    # Extract known properties
    rfonts = rpr.find("w:rFonts", NAMESPACES)
    if rfonts is not None:
        w_ns = NAMESPACES["w"]
        for attr_name in ("ascii", "hAnsi", "cs", "eastAsia"):
            val = rfonts.get(f"{{{w_ns}}}{attr_name}")
            if val is not None:
                fmt[f"font_{attr_name}"] = val

    sz = rpr.find("w:sz", NAMESPACES)
    if sz is not None:
        val = sz.get(f'{{{NAMESPACES["w"]}}}val')
        if val is not None:
            fmt["sz"] = val

    sz_cs = rpr.find("w:szCs", NAMESPACES)
    if sz_cs is not None:
        val = sz_cs.get(f'{{{NAMESPACES["w"]}}}val')
        if val is not None:
            fmt["szCs"] = val

    if rpr.find("w:b", NAMESPACES) is not None:
        fmt["bold"] = True

    if rpr.find("w:i", NAMESPACES) is not None:
        fmt["italic"] = True

    if rpr.find("w:u", NAMESPACES) is not None:
        u_elem = rpr.find("w:u", NAMESPACES)
        val = u_elem.get(f'{{{NAMESPACES["w"]}}}val')
        fmt["underline"] = val or "single"

    color = rpr.find("w:color", NAMESPACES)
    if color is not None:
        val = color.get(f'{{{NAMESPACES["w"]}}}val')
        if val is not None:
            fmt["color"] = val

    return fmt


def build_run_xml(text: str, formatting: dict) -> str:
    """Build a <w:r> element with the given text and inherited formatting.

    Returns a string of well-formed OOXML.
    """
    w = NAMESPACES["w"]

    r_elem = etree.Element(f"{{{w}}}r")

    # Build rPr if there's any formatting
    if formatting:
        rpr = etree.SubElement(r_elem, f"{{{w}}}rPr")

        # Font
        font_attrs = {}
        for key in ("font_ascii", "font_hAnsi", "font_cs", "font_eastAsia"):
            if key in formatting:
                attr_name = key.replace("font_", "")
                font_attrs[f"{{{w}}}{attr_name}"] = formatting[key]
        if font_attrs:
            etree.SubElement(rpr, f"{{{w}}}rFonts", font_attrs)

        # Bold
        if formatting.get("bold"):
            etree.SubElement(rpr, f"{{{w}}}b")

        # Italic
        if formatting.get("italic"):
            etree.SubElement(rpr, f"{{{w}}}i")

        # Underline
        if "underline" in formatting:
            etree.SubElement(rpr, f"{{{w}}}u", {f"{{{w}}}val": formatting["underline"]})

        # Size
        if "sz" in formatting:
            etree.SubElement(rpr, f"{{{w}}}sz", {f"{{{w}}}val": formatting["sz"]})

        if "szCs" in formatting:
            etree.SubElement(rpr, f"{{{w}}}szCs", {f"{{{w}}}val": formatting["szCs"]})

        # Color
        if "color" in formatting:
            etree.SubElement(rpr, f"{{{w}}}color", {f"{{{w}}}val": formatting["color"]})

    # Text element
    t_elem = etree.SubElement(r_elem, f"{{{w}}}t")
    t_elem.text = text
    # Preserve spaces
    if text and (text[0] == " " or text[-1] == " "):
        t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    return etree.tostring(r_elem, encoding="unicode")


def is_well_formed_ooxml(xml_string: str) -> tuple[bool, str | None]:
    """Check that *xml_string* is well-formed XML using only legitimate OOXML
    elements and attributes.

    Returns (True, None) on success, (False, error_message) on failure.
    """
    # Try to parse with namespace declarations
    wrapped = (
        f'<_wrapper xmlns:w="{NAMESPACES["w"]}" '
        f'xmlns:r="{NAMESPACES["r"]}" '
        f'xmlns:wp="{NAMESPACES["wp"]}">'
        f"{xml_string}</_wrapper>"
    )
    try:
        root = etree.fromstring(wrapped.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        return False, f"XML syntax error: {e}"

    # Check all elements use allowed names
    for elem in root.iter():
        if elem.tag == "_wrapper":
            continue
        tag = elem.tag
        # Extract local name
        if tag.startswith("{"):
            uri, local = tag[1:].split("}", 1)
            # Must be a known namespace
            if uri not in _URI_TO_PREFIX:
                return False, f"Unknown namespace: {uri}"
        else:
            local = tag

        if local not in _ALLOWED_OOXML_ELEMENTS:
            return False, f"Disallowed element: {local}"

    return True, None
