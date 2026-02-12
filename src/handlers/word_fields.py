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

"""Word (.docx) form field detection — find fillable targets in documents.

Uses heuristics to detect likely answer locations: empty table cells adjacent
to cells with question text, and paragraphs containing placeholder patterns
like [Enter here] or ___.
"""

from __future__ import annotations

import re

from lxml import etree

from src.models import FormField
from src.xml_utils import NAMESPACES, SECURE_PARSER

WORD_NAMESPACE_URI = NAMESPACES["w"]


def _get_context_text(element: etree._Element, max_chars: int = 100) -> str:
    """Get text content from an element, truncated for human review context."""
    texts: list[str] = []
    for t_elem in element.iter(f"{{{WORD_NAMESPACE_URI}}}t"):
        if t_elem.text:
            texts.append(t_elem.text)
    text = " ".join(texts)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def _find_empty_table_cells(
    body: etree._Element, start_id: int
) -> tuple[list[FormField], int]:
    """Find empty table cells following cells with text (Q/A pattern).

    Returns the list of detected fields and the next available field_id counter.
    """
    fields: list[FormField] = []
    counter = start_id

    for tbl in body.iter(f"{{{WORD_NAMESPACE_URI}}}tbl"):
        for tr in tbl.iter(f"{{{WORD_NAMESPACE_URI}}}tr"):
            cells = list(tr.iter(f"{{{WORD_NAMESPACE_URI}}}tc"))
            for i in range(len(cells) - 1):
                q_text = _get_context_text(cells[i]).strip()
                a_text = _get_context_text(cells[i + 1]).strip()
                if q_text and not a_text:
                    counter += 1
                    fields.append(FormField(
                        field_id=f"field_{counter}",
                        label=q_text,
                        field_type="table_cell",
                    ))

    return fields, counter


def _find_placeholder_paragraphs(
    body: etree._Element, start_id: int
) -> list[FormField]:
    """Find paragraphs containing placeholder patterns ([Enter ...], ___).

    Returns the list of detected placeholder fields.
    """
    placeholder_patterns = [
        re.compile(r"\[Enter[^\]]*\]"),
        re.compile(r"_{3,}"),
    ]
    fields: list[FormField] = []
    counter = start_id

    for p_elem in body.iter(f"{{{WORD_NAMESPACE_URI}}}p"):
        p_text = _get_context_text(p_elem)
        for pattern in placeholder_patterns:
            match = pattern.search(p_text)
            if match:
                counter += 1
                fields.append(FormField(
                    field_id=f"field_{counter}",
                    label=p_text.strip(),
                    field_type="placeholder",
                    current_value=match.group(),
                ))
                break  # One field per paragraph

    return fields


def list_form_fields(doc_xml: bytes) -> list[FormField]:
    """Detect empty table cells and placeholder text as fillable targets.

    doc_xml: raw word/document.xml bytes from the .docx archive.
    """
    root = etree.fromstring(doc_xml, SECURE_PARSER)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        return []

    table_fields, next_id = _find_empty_table_cells(body, 0)
    placeholder_fields = _find_placeholder_paragraphs(body, next_id)
    return table_fields + placeholder_fields
