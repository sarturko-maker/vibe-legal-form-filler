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

"""Word element analysis — text extraction, formatting hints, complexity detection.

Helpers used by word_indexer.py to analyse individual OOXML elements and
produce compact representations. Separated to keep word_indexer focused on
tree walking and ID assignment.
"""

from __future__ import annotations

import re

from lxml import etree

from src.xml_utils import NAMESPACES

W = NAMESPACES["w"]

# Elements that make a cell or paragraph "complex" and require raw XML
COMPLEX_TAGS = {
    f"{{{W}}}sdt",           # content controls
    f"{{{W}}}fldChar",       # legacy form fields
    f"{{{W}}}txbxContent",   # text boxes
    f"{{{W}}}object",        # embedded objects
}

PLACEHOLDER_RE = re.compile(r"\[Enter[^\]]*\]|_{3,}")


def get_text(element: etree._Element) -> str:
    """Extract all text from w:t elements, joined with no separator."""
    parts: list[str] = []
    for t_elem in element.iter(f"{{{W}}}t"):
        if t_elem.text:
            parts.append(t_elem.text)
    return "".join(parts)


def get_formatting_hints(element: etree._Element, text: str) -> list[str]:
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


def is_answer_target(text: str) -> bool:
    """Return True if text indicates an answer target (empty or placeholder)."""
    stripped = text.strip()
    return not stripped or bool(PLACEHOLDER_RE.search(stripped))


def get_target_marker(text: str) -> str:
    """Return an answer target marker if text is empty or a placeholder."""
    if is_answer_target(text):
        return " ← answer target"
    return ""


def detect_complex(element: etree._Element) -> str | None:
    """Check if element contains complex OOXML that can't be compacted.

    Returns a string describing the complexity type, or None if simple.
    """
    for tag in COMPLEX_TAGS:
        if element.find(f".//{tag}") is not None:
            local = tag.split("}")[-1]
            return local

    # Nested tables (table inside a table cell)
    if etree.QName(element).localname == "tc":
        nested = element.findall(f".//{{{W}}}tbl")
        if nested:
            return "nested_table"

    # gridSpan (merged cells)
    grid_span = element.find(f".//{{{W}}}gridSpan")
    if grid_span is not None:
        val = grid_span.get(f"{{{W}}}val", "")
        if val and val != "1":
            return f"gridSpan={val}"

    # vMerge (vertically merged cells)
    if element.find(f".//{{{W}}}vMerge") is not None:
        return "vMerge"

    return None
