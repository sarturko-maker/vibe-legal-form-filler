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

"""Word (.docx) location validation — confirm element IDs and snippets exist.

Matches each location (element ID like T1-R2-C2 or OOXML snippet) against
the document body. Returns match status and XPath for each location.
"""

from __future__ import annotations

import re

from lxml import etree

from src.models import (
    LocationSnippet,
    LocationStatus,
    ValidatedLocation,
)
from src.xml_utils import NAMESPACES, SECURE_PARSER, find_snippet_in_body

from src.handlers.word_element_analysis import get_text, is_answer_target
from src.handlers.word_fields import _get_context_text
from src.handlers.word_parser import get_body_xml

# Matches element IDs from compact extraction: T1-R2-C2 or P5
ELEMENT_ID_RE = re.compile(r"^(T\d+-R\d+-C\d+|P\d+)$")
TABLE_CELL_RE = re.compile(r"^T(\d+)-R(\d+)-C(\d+)$")


def _is_element_id(snippet: str) -> bool:
    """Check if a snippet looks like an element ID (T1-R2-C2 or P5)."""
    return bool(ELEMENT_ID_RE.match(snippet.strip()))


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Match each location against the document body.

    Accepts element IDs (T1-R2-C2, P5) or OOXML snippets.
    """
    body_xml = get_body_xml(file_bytes)
    body_root = etree.fromstring(body_xml.encode("utf-8"), SECURE_PARSER)

    # Build id_to_xpath mapping once if any location is an element ID
    id_to_xpath: dict[str, str] | None = None
    if any(_is_element_id(loc.snippet) for loc in locations):
        from src.handlers.word_indexer import extract_structure_compact
        compact = extract_structure_compact(file_bytes)
        id_to_xpath = compact.id_to_xpath

    results: list[ValidatedLocation] = []
    for loc in locations:
        if _is_element_id(loc.snippet):
            results.append(
                _validate_element_id(loc, id_to_xpath, body_root)
            )
        else:
            results.append(
                _validate_snippet(loc, body_xml, body_root)
            )

    return results


def _validate_element_id(
    loc: LocationSnippet,
    id_to_xpath: dict[str, str],
    body_root: etree._Element,
) -> ValidatedLocation:
    """Validate a location by looking up its element ID in the id_to_xpath mapping."""
    element_id = loc.snippet.strip()
    xpath = id_to_xpath.get(element_id)
    if xpath is None:
        return ValidatedLocation(
            pair_id=loc.pair_id,
            status=LocationStatus.NOT_FOUND,
        )
    matched = body_root.xpath(xpath, namespaces=NAMESPACES)
    context = ""
    if matched:
        context = _get_context_text(matched[0])
    warning = _check_question_cell_warning(
        element_id, matched[0] if matched else None, id_to_xpath
    )
    if warning:
        context = f"{warning}\n{context}" if context else warning
    return ValidatedLocation(
        pair_id=loc.pair_id,
        status=LocationStatus.MATCHED,
        xpath=xpath,
        context=context,
    )


def _check_question_cell_warning(
    element_id: str,
    element: etree._Element | None,
    id_to_xpath: dict[str, str],
) -> str:
    """Warn if a table cell contains text and looks like a question, not an answer.

    Returns a warning string, or empty string if no concern.
    """
    if element is None:
        return ""
    match = TABLE_CELL_RE.match(element_id)
    if not match:
        return ""
    text = get_text(element)
    if is_answer_target(text):
        return ""

    tbl, row, col = match.group(1), match.group(2), match.group(3)
    preview = text[:60] + ("..." if len(text) > 60 else "")
    suggestion = _suggest_answer_cell(tbl, row, col, id_to_xpath)
    msg = (
        f"WARNING: {element_id} contains existing text: "
        f"'{preview}' — this looks like a question cell, "
        f"not an answer target."
    )
    if suggestion:
        msg += f" Did you mean {suggestion}?"
    return msg


def _suggest_answer_cell(
    tbl: str, row: str, col: str, id_to_xpath: dict[str, str]
) -> str:
    """Suggest the next cell in the same row as a likely answer target."""
    next_col = int(col) + 1
    candidate = f"T{tbl}-R{row}-C{next_col}"
    if candidate in id_to_xpath:
        return candidate
    return ""


def _validate_snippet(
    loc: LocationSnippet,
    body_xml: str,
    body_root: etree._Element,
) -> ValidatedLocation:
    """Validate a location by searching for its OOXML snippet in the document."""
    xpaths = find_snippet_in_body(body_xml, loc.snippet)

    if len(xpaths) == 0:
        return ValidatedLocation(
            pair_id=loc.pair_id,
            status=LocationStatus.NOT_FOUND,
        )
    if len(xpaths) == 1:
        matched = body_root.xpath(xpaths[0], namespaces=NAMESPACES)
        context = ""
        if matched:
            context = _get_context_text(matched[0])
        return ValidatedLocation(
            pair_id=loc.pair_id,
            status=LocationStatus.MATCHED,
            xpath=xpaths[0],
            context=context,
        )
    return ValidatedLocation(
        pair_id=loc.pair_id,
        status=LocationStatus.AMBIGUOUS,
        context=f"Snippet matched {len(xpaths)} locations",
    )
