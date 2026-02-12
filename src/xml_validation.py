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

"""OOXML validation — check that XML snippets are well-formed and use only
legitimate OOXML elements.

Used by word.py to validate AI-generated structured insertion XML before
writing it into a document.
"""

from __future__ import annotations

from lxml import etree

from src.xml_snippet_matching import NAMESPACES, SECURE_PARSER

# Reverse mapping for namespace validation
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


def is_well_formed_ooxml(xml_string: str) -> tuple[bool, str | None]:
    """Check that *xml_string* is well-formed XML using only legitimate OOXML
    elements and attributes.

    Returns (True, None) on success, (False, error_message) on failure.
    """
    wrapped = (
        f'<_wrapper xmlns:w="{NAMESPACES["w"]}" '
        f'xmlns:r="{NAMESPACES["r"]}" '
        f'xmlns:wp="{NAMESPACES["wp"]}">'
        f"{xml_string}</_wrapper>"
    )
    try:
        root = etree.fromstring(wrapped.encode("utf-8"), SECURE_PARSER)
    except etree.XMLSyntaxError as e:
        return False, f"XML syntax error: {e}"

    for elem in root.iter():
        if elem.tag == "_wrapper":
            continue
        tag = elem.tag
        if tag.startswith("{"):
            uri, local = tag[1:].split("}", 1)
            if uri not in _URI_TO_PREFIX:
                return False, f"Unknown namespace: {uri}"
        else:
            local = tag

        if local not in _ALLOWED_OOXML_ELEMENTS:
            return False, f"Disallowed element: {local}"

    return True, None
