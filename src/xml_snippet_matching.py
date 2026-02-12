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

"""OOXML snippet matching — find where an XML snippet occurs in a document body.

Contains the core matching logic: parsing snippets, structural comparison of
elements, XPath generation for matched locations. Used by word.py to implement
validate_locations.
"""

from __future__ import annotations

from lxml import etree

# OOXML namespaces (canonical source — shared across all XML modules)
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

# Reverse mapping: full URI -> prefix
_URI_TO_PREFIX = {v: k for k, v in NAMESPACES.items()}


def parse_snippet(snippet: str) -> etree._Element | None:
    """Parse an OOXML snippet string into an lxml element.

    If the snippet doesn't include namespace declarations, wraps it in a
    temporary element with the standard OOXML namespace declarations and
    returns the first child. Returns None if the snippet is not valid XML.
    """
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


def _build_xpath(element: etree._Element, root: etree._Element) -> str:
    """Build an XPath expression from *root* down to *element*.

    Walks up the tree from element to root, building positional predicates
    (e.g. w:tr[2]) when siblings share the same tag.
    """
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


def _elements_structurally_equal(a: etree._Element, b: etree._Element) -> bool:
    """Recursively compare two lxml elements for structural equality.

    Ignores namespace declarations (which vary depending on tree context)
    and normalises whitespace in text content.
    """
    if a.tag != b.tag:
        return False

    if dict(a.attrib) != dict(b.attrib):
        return False

    a_text = (a.text or "").strip()
    b_text = (b.text or "").strip()
    if a_text != b_text:
        return False

    a_tail = (a.tail or "").strip()
    b_tail = (b.tail or "").strip()
    if a_tail != b_tail:
        return False

    a_children = list(a)
    b_children = list(b)
    if len(a_children) != len(b_children):
        return False

    return all(
        _elements_structurally_equal(ac, bc)
        for ac, bc in zip(a_children, b_children)
    )


def find_snippet_in_body(body_xml: str, snippet: str) -> list[str]:
    """Find all XPaths where *snippet* matches within the document body.

    The snippet is parsed as XML and then compared structurally against every
    element of the same type in the body tree. Comparison ignores namespace
    declarations and normalises whitespace.

    Returns a list of XPath strings. Empty list means no match, more than one
    means ambiguous.
    """
    body_root = etree.fromstring(body_xml.encode("utf-8"))

    snippet_elem = parse_snippet(snippet)
    if snippet_elem is None:
        return []

    snippet_tag = snippet_elem.tag

    matches: list[str] = []
    for elem in body_root.iter(snippet_tag):
        if _elements_structurally_equal(elem, snippet_elem):
            xpath = _build_xpath(elem, body_root)
            matches.append(xpath)

    return matches
