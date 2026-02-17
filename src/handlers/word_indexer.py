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

import zipfile
from io import BytesIO

from lxml import etree

from src.models import CompactStructureResponse
from src.xml_utils import NAMESPACES, SECURE_PARSER, build_xpath

from src.handlers.word_element_analysis import (
    detect_complex,
    get_formatting_hints,
    get_target_marker,
    get_text,
    is_answer_target,
)


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
        cell_roles = _detect_row_roles(cells)
        for c_idx, cell in enumerate(cells, start=1):
            element_id = f"T{tbl_num}-R{r_idx}-C{c_idx}"
            xpath = build_xpath(cell, body)
            id_to_xpath[element_id] = xpath
            _index_cell(cell, element_id, lines, complex_elements,
                        role=cell_roles.get(c_idx))


def _detect_row_roles(cells: list[etree._Element]) -> dict[int, str]:
    """Detect question/answer roles for cells in a table row.

    If a row has at least one answer target (empty/placeholder), mark
    non-empty cells as 'question' and answer targets as 'answer'.
    Rows with no answer targets (e.g. header rows) get no roles.

    Returns a dict from 1-based column index to role string.
    """
    texts = {i: get_text(cell) for i, cell in enumerate(cells, start=1)}
    has_answer = any(is_answer_target(t) for t in texts.values())
    if not has_answer:
        return {}
    roles: dict[int, str] = {}
    for col_idx, text in texts.items():
        if is_answer_target(text):
            roles[col_idx] = "answer"
        else:
            roles[col_idx] = "question"
    return roles


def _index_cell(
    cell: etree._Element,
    element_id: str,
    lines: list[str],
    complex_elements: list[str],
    role: str | None = None,
) -> None:
    """Build a compact line for a single table cell."""
    complex_type = detect_complex(cell)
    if complex_type:
        complex_elements.append(element_id)
        raw_snippet = etree.tostring(cell, encoding="unicode")
        if len(raw_snippet) > 500:
            raw_snippet = raw_snippet[:500] + "..."
        lines.append(f'{element_id}: COMPLEX({complex_type}): {raw_snippet}')
        return

    text = get_text(cell)
    hints = get_formatting_hints(cell, text)
    if role:
        hints.append(role)
    target_marker = get_target_marker(text)
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
    xpath = build_xpath(para, body)
    id_to_xpath[element_id] = xpath

    complex_type = detect_complex(para)
    if complex_type:
        complex_elements.append(element_id)
        raw_snippet = etree.tostring(para, encoding="unicode")
        if len(raw_snippet) > 500:
            raw_snippet = raw_snippet[:500] + "..."
        lines.append(f'{element_id}: COMPLEX({complex_type}): {raw_snippet}')
        return

    text = get_text(para)
    hints = get_formatting_hints(para, text)
    target_marker = get_target_marker(text)
    hint_str = f" [{', '.join(hints)}]" if hints else ""
    lines.append(f'{element_id}: "{text}"{hint_str}{target_marker}')
