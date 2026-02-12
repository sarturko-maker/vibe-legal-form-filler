# Copyright (C) 2025 the contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""OOXML formatting — extract formatting from elements and build formatted runs.

Used by word.py to implement build_insertion_xml (formatting inheritance for
plain text answers). Extraction reads formatting properties from existing
document elements; building creates new OOXML runs with those properties.
"""

from __future__ import annotations

from lxml import etree

from src.xml_snippet_matching import NAMESPACES


def _find_run_properties(elem: etree._Element) -> etree._Element | None:
    """Find the <w:rPr> element to extract formatting from.

    Searches in order: direct child rPr (if element is a run), first run's
    rPr (if element is a paragraph), paragraph-level rPr inside pPr.
    """
    rpr = elem.find("w:rPr", NAMESPACES)
    if rpr is not None:
        return rpr

    first_run = elem.find(".//w:r", NAMESPACES)
    if first_run is not None:
        rpr = first_run.find("w:rPr", NAMESPACES)
        if rpr is not None:
            return rpr

    ppr = elem.find("w:pPr", NAMESPACES)
    if ppr is not None:
        return ppr.find("w:rPr", NAMESPACES)

    return None


def _extract_font_properties(rpr: etree._Element) -> dict:
    """Extract font family properties (ascii, hAnsi, cs, eastAsia) from rPr."""
    formatting: dict = {}
    rfonts = rpr.find("w:rFonts", NAMESPACES)
    if rfonts is not None:
        w_ns = NAMESPACES["w"]
        for attr_name in ("ascii", "hAnsi", "cs", "eastAsia"):
            val = rfonts.get(f"{{{w_ns}}}{attr_name}")
            if val is not None:
                formatting[f"font_{attr_name}"] = val
    return formatting


def _extract_size_properties(rpr: etree._Element) -> dict:
    """Extract font size properties (sz, szCs) from rPr."""
    formatting: dict = {}
    w_ns = NAMESPACES["w"]

    sz = rpr.find("w:sz", NAMESPACES)
    if sz is not None:
        val = sz.get(f"{{{w_ns}}}val")
        if val is not None:
            formatting["sz"] = val

    sz_cs = rpr.find("w:szCs", NAMESPACES)
    if sz_cs is not None:
        val = sz_cs.get(f"{{{w_ns}}}val")
        if val is not None:
            formatting["szCs"] = val

    return formatting


def _extract_style_properties(rpr: etree._Element) -> dict:
    """Extract bold, italic, and underline properties from rPr."""
    formatting: dict = {}

    if rpr.find("w:b", NAMESPACES) is not None:
        formatting["bold"] = True

    if rpr.find("w:i", NAMESPACES) is not None:
        formatting["italic"] = True

    if rpr.find("w:u", NAMESPACES) is not None:
        u_elem = rpr.find("w:u", NAMESPACES)
        val = u_elem.get(f'{{{NAMESPACES["w"]}}}val')
        formatting["underline"] = val or "single"

    return formatting


def _extract_color_properties(rpr: etree._Element) -> dict:
    """Extract text color from rPr."""
    formatting: dict = {}
    color = rpr.find("w:color", NAMESPACES)
    if color is not None:
        val = color.get(f'{{{NAMESPACES["w"]}}}val')
        if val is not None:
            formatting["color"] = val
    return formatting


def _parse_element_xml(element_xml: str) -> etree._Element:
    """Parse an OOXML element string, adding namespace wrappers if needed."""
    try:
        return etree.fromstring(element_xml.encode("utf-8"))
    except etree.XMLSyntaxError:
        wrapper = (
            f'<_wrapper xmlns:w="{NAMESPACES["w"]}" '
            f'xmlns:r="{NAMESPACES["r"]}">'
            f"{element_xml}</_wrapper>"
        )
        return etree.fromstring(wrapper.encode("utf-8"))[0]


def extract_formatting(element_xml: str) -> dict:
    """Extract run-level formatting from an OOXML element as a plain dict.

    Looks for <w:rPr> within the element and extracts known formatting
    properties (font, size, bold, italic, underline, color). If the element
    is a paragraph, looks at the first run's properties or the paragraph-level
    rPr.
    """
    elem = _parse_element_xml(element_xml)
    rpr = _find_run_properties(elem)
    if rpr is None:
        return {}

    formatting: dict = {}
    formatting.update(_extract_font_properties(rpr))
    formatting.update(_extract_size_properties(rpr))
    formatting.update(_extract_style_properties(rpr))
    formatting.update(_extract_color_properties(rpr))
    return formatting


def _apply_font_properties(rpr: etree._Element, formatting: dict) -> None:
    """Add <w:rFonts> to rPr from formatting dict."""
    w = NAMESPACES["w"]
    font_attrs = {}
    for key in ("font_ascii", "font_hAnsi", "font_cs", "font_eastAsia"):
        if key in formatting:
            attr_name = key.replace("font_", "")
            font_attrs[f"{{{w}}}{attr_name}"] = formatting[key]
    if font_attrs:
        etree.SubElement(rpr, f"{{{w}}}rFonts", font_attrs)


def _apply_style_properties(rpr: etree._Element, formatting: dict) -> None:
    """Add bold, italic, and underline elements to rPr from formatting dict."""
    w = NAMESPACES["w"]
    if formatting.get("bold"):
        etree.SubElement(rpr, f"{{{w}}}b")
    if formatting.get("italic"):
        etree.SubElement(rpr, f"{{{w}}}i")
    if "underline" in formatting:
        etree.SubElement(rpr, f"{{{w}}}u", {f"{{{w}}}val": formatting["underline"]})


def _apply_size_properties(rpr: etree._Element, formatting: dict) -> None:
    """Add <w:sz> and <w:szCs> elements to rPr from formatting dict."""
    w = NAMESPACES["w"]
    if "sz" in formatting:
        etree.SubElement(rpr, f"{{{w}}}sz", {f"{{{w}}}val": formatting["sz"]})
    if "szCs" in formatting:
        etree.SubElement(rpr, f"{{{w}}}szCs", {f"{{{w}}}val": formatting["szCs"]})


def _apply_color_properties(rpr: etree._Element, formatting: dict) -> None:
    """Add <w:color> element to rPr from formatting dict."""
    w = NAMESPACES["w"]
    if "color" in formatting:
        etree.SubElement(rpr, f"{{{w}}}color", {f"{{{w}}}val": formatting["color"]})


def build_run_xml(text: str, formatting: dict) -> str:
    """Build a <w:r> element with the given text and inherited formatting.

    Returns a string of well-formed OOXML.
    """
    w = NAMESPACES["w"]
    r_elem = etree.Element(f"{{{w}}}r")

    if formatting:
        rpr = etree.SubElement(r_elem, f"{{{w}}}rPr")
        _apply_font_properties(rpr, formatting)
        _apply_style_properties(rpr, formatting)
        _apply_size_properties(rpr, formatting)
        _apply_color_properties(rpr, formatting)

    t_elem = etree.SubElement(r_elem, f"{{{w}}}t")
    t_elem.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    return etree.tostring(r_elem, encoding="unicode")
