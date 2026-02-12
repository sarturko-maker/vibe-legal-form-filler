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

"""Compact extraction — walks OOXML body and builds an indexed representation.

Assigns stable element IDs (T1-R2-C1 for table cells, P5 for paragraphs),
extracts text content, detects formatting hints, marks answer targets, and
flags complex elements. Returns a CompactStructureResponse with compact_text,
id_to_xpath mapping, and complex_elements list.

This is the primary extraction tool for agents with normal context windows.
The output is a few KB instead of ~134KB of raw OOXML.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO

from lxml import etree

from src.models import CompactStructureResponse
from src.xml_utils import NAMESPACES, SECURE_PARSER

W = NAMESPACES["w"]

# Elements that make a cell or paragraph "complex" and require raw XML
COMPLEX_TAGS = {
    f"{{{W}}}sdt",           # content controls
    f"{{{W}}}fldChar",       # legacy form fields
    f"{{{W}}}txbxContent",   # text boxes
    f"{{{W}}}object",        # embedded objects
}

PLACEHOLDER_RE = re.compile(r"\[Enter[^\]]*\]|_{3,}")


def extract_structure_compact(file_bytes: bytes) -> CompactStructureResponse:
    """Walk the .docx body and return a compact indexed representation.

    file_bytes: raw .docx file bytes.
    Returns CompactStructureResponse with compact_text, id_to_xpath, and
    complex_elements.
    """
    body = _parse_body(file_bytes)
    lines: list[str] = []
    id_to_xpath: dict[str, str] = {}
    complex_elements: list[str] = []

    p_counter = 0
    t_counter = 0

    for child in body:
        tag = etree.QName(child).localname
        if tag == "tbl":
            t_counter += 1
            _index_table(
                child, t_counter, body, lines, id_to_xpath, complex_elements
            )
        elif tag == "p":
            p_counter += 1
            _index_paragraph(
                child, f"P{p_counter}", body, lines, id_to_xpath,
                complex_elements
            )

    return CompactStructureResponse(
        compact_text="\n".join(lines),
        id_to_xpath=id_to_xpath,
        complex_elements=complex_elements,
    )


def _parse_body(file_bytes: bytes) -> etree._Element:
    """Extract and parse <w:body> from a .docx file."""
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        doc_xml = zf.read("word/document.xml")
    root = etree.fromstring(doc_xml, SECURE_PARSER)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")
    return body


def _index_table(
    tbl: etree._Element,
    tbl_num: int,
    body: etree._Element,
    lines: list[str],
    id_to_xpath: dict[str, str],
    complex_elements: list[str],
) -> None:
    """Index all rows and cells in a table."""
    rows = tbl.findall("w:tr", NAMESPACES)
    for r_idx, row in enumerate(rows, start=1):
        cells = row.findall("w:tc", NAMESPACES)
        for c_idx, cell in enumerate(cells, start=1):
            element_id = f"T{tbl_num}-R{r_idx}-C{c_idx}"
            xpath = _build_xpath_to(cell, body)
            id_to_xpath[element_id] = xpath
            _index_cell(
                cell, element_id, lines, complex_elements
            )


def _index_cell(
    cell: etree._Element,
    element_id: str,
    lines: list[str],
    complex_elements: list[str],
) -> None:
    """Build a compact line for a single table cell."""
    complex_type = _detect_complex(cell)
    if complex_type:
        complex_elements.append(element_id)
        raw_snippet = etree.tostring(cell, encoding="unicode")
        # Truncate very large snippets
        if len(raw_snippet) > 500:
            raw_snippet = raw_snippet[:500] + "..."
        lines.append(f'{element_id}: COMPLEX({complex_type}): {raw_snippet}')
        return

    text = _get_text(cell)
    hints = _get_formatting_hints(cell, text)
    target_marker = _get_target_marker(text)
    hint_str = f" [{', '.join(hints)}]" if hints else ""
    lines.append(f'{element_id}: "{text}"{hint_str}{target_marker}')


def _index_paragraph(
    para: etree._Element,
    element_id: str,
    body: etree._Element,
    lines: list[str],
    id_to_xpath: dict[str, str],
    complex_elements: list[str],
) -> None:
    """Build a compact line for a top-level paragraph."""
    xpath = _build_xpath_to(para, body)
    id_to_xpath[element_id] = xpath

    complex_type = _detect_complex(para)
    if complex_type:
        complex_elements.append(element_id)
        raw_snippet = etree.tostring(para, encoding="unicode")
        if len(raw_snippet) > 500:
            raw_snippet = raw_snippet[:500] + "..."
        lines.append(f'{element_id}: COMPLEX({complex_type}): {raw_snippet}')
        return

    text = _get_text(para)
    hints = _get_formatting_hints(para, text)
    target_marker = _get_target_marker(text)
    hint_str = f" [{', '.join(hints)}]" if hints else ""
    lines.append(f'{element_id}: "{text}"{hint_str}{target_marker}')


def _get_text(element: etree._Element) -> str:
    """Extract all text from w:t elements, joined with no separator."""
    parts: list[str] = []
    for t_elem in element.iter(f"{{{W}}}t"):
        if t_elem.text:
            parts.append(t_elem.text)
    return "".join(parts)


def _get_formatting_hints(element: etree._Element, text: str) -> list[str]:
    """Detect bold, italic, shading, empty, and placeholder on an element."""
    hints: list[str] = []

    if not text.strip():
        hints.append("empty")
    elif PLACEHOLDER_RE.search(text):
        hints.append("placeholder")

    if element.find(f".//{{{W}}}b") is not None:
        hints.append("bold")
    if element.find(f".//{{{W}}}i") is not None:
        hints.append("italic")
    shd = element.find(f".//{{{W}}}shd")
    if shd is not None:
        fill = shd.get(f"{{{W}}}fill", "")
        if fill and fill.lower() not in ("", "auto", "ffffff"):
            hints.append("shaded")
    return hints


def _get_target_marker(text: str) -> str:
    """Return an answer target marker if text is empty or a placeholder."""
    stripped = text.strip()
    if not stripped:
        return " ← answer target"
    if PLACEHOLDER_RE.search(stripped):
        return " ← answer target"
    return ""


def _detect_complex(element: etree._Element) -> str | None:
    """Check if element contains complex OOXML that can't be compacted.

    Returns a string describing the complexity type, or None if simple.
    """
    # Check for complex child tags
    for tag in COMPLEX_TAGS:
        if element.find(f".//{tag}") is not None:
            local = tag.split("}")[-1]
            return local

    # Check for nested tables (table inside a table cell)
    if etree.QName(element).localname == "tc":
        nested = element.findall(f".//{{{W}}}tbl")
        if nested:
            return "nested_table"

    # Check for gridSpan (merged cells)
    grid_span = element.find(f".//{{{W}}}gridSpan")
    if grid_span is not None:
        val = grid_span.get(f"{{{W}}}val", "")
        if val and val != "1":
            return f"gridSpan={val}"

    # Check for vMerge (vertically merged cells)
    if element.find(f".//{{{W}}}vMerge") is not None:
        return "vMerge"

    return None


def _build_xpath_to(
    target: etree._Element, root: etree._Element
) -> str:
    """Build an XPath from root to target using positional predicates."""
    parts: list[str] = []
    current = target
    while current is not root and current is not None:
        tag = current.tag
        qname = _clark_to_prefixed(tag)
        parent = current.getparent()
        if parent is not None:
            same = [c for c in parent if c.tag == current.tag]
            if len(same) > 1:
                pos = same.index(current) + 1
                qname = f"{qname}[{pos}]"
        parts.append(qname)
        current = parent
    parts.reverse()
    return "./" + "/".join(parts)


# Reverse mapping: full URI -> prefix
_URI_TO_PREFIX = {v: k for k, v in NAMESPACES.items()}


def _clark_to_prefixed(tag: str) -> str:
    """Convert Clark notation {uri}local to prefix:local."""
    if not tag.startswith("{"):
        return tag
    uri, local = tag[1:].split("}", 1)
    prefix = _URI_TO_PREFIX.get(uri)
    if prefix:
        return f"{prefix}:{local}"
    return local
