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

"""Word (.docx) handler — extract, validate, build XML, write.

This is the main entry point for all Word document operations. Extract and
validate logic lives here; write and field detection are in word_writer.py
and word_fields.py respectively.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO

from lxml import etree

from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    BuildInsertionXmlResponse,
    ExtractStructureResponse,
    FormField,
    LocationSnippet,
    LocationStatus,
    ValidatedLocation,
)
from src.xml_utils import (
    NAMESPACES,
    build_run_xml,
    extract_formatting,
    find_snippet_in_body,
    is_well_formed_ooxml,
)

from src.handlers.word_fields import (
    _get_context_text,
    list_form_fields as _list_form_fields_impl,
)
from src.handlers.word_writer import write_answers as _write_answers_impl

WORD_NAMESPACE_URI = NAMESPACES["w"]

# Matches element IDs from compact extraction: T1-R2-C2 or P5
ELEMENT_ID_RE = re.compile(r"^(T\d+-R\d+-C\d+|P\d+)$")


def _read_document_xml(file_bytes: bytes) -> bytes:
    """Extract word/document.xml from a .docx ZIP archive."""
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        return zf.read("word/document.xml")


def _get_body_xml(file_bytes: bytes) -> str:
    """Extract the <w:body> XML string from a .docx file."""
    doc_xml = _read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")
    return etree.tostring(body, encoding="unicode")


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Read a .docx and return the full <w:body> XML as a string."""
    body_xml = _get_body_xml(file_bytes)
    return ExtractStructureResponse(body_xml=body_xml)


def _is_element_id(snippet: str) -> bool:
    """Check if a snippet looks like an element ID (T1-R2-C2 or P5)."""
    return bool(ELEMENT_ID_RE.match(snippet.strip()))


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Match each location against the document body.

    Accepts element IDs (T1-R2-C2, P5) or OOXML snippets.
    """
    body_xml = _get_body_xml(file_bytes)
    body_root = etree.fromstring(body_xml.encode("utf-8"))

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
    return ValidatedLocation(
        pair_id=loc.pair_id,
        status=LocationStatus.MATCHED,
        xpath=xpath,
        context=context,
    )


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


def build_insertion_xml(request: BuildInsertionXmlRequest) -> BuildInsertionXmlResponse:
    """Build a <w:r> element inheriting formatting from the target location.

    For plain_text: extract formatting from target_context_xml and wrap
    answer_text in a <w:r> with that formatting.

    For structured: validate the AI-provided OOXML.
    """
    if request.answer_type == AnswerType.PLAIN_TEXT:
        formatting = extract_formatting(request.target_context_xml)
        run_xml = build_run_xml(request.answer_text, formatting)
        return BuildInsertionXmlResponse(insertion_xml=run_xml, valid=True)

    elif request.answer_type == AnswerType.STRUCTURED:
        valid, error = is_well_formed_ooxml(request.answer_text)
        if valid:
            return BuildInsertionXmlResponse(
                insertion_xml=request.answer_text, valid=True
            )
        else:
            return BuildInsertionXmlResponse(
                insertion_xml="", valid=False, error=error
            )

    return BuildInsertionXmlResponse(
        insertion_xml="", valid=False,
        error=f"Unknown answer_type: {request.answer_type}",
    )


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Insert answers at the specified XPaths and return the modified .docx bytes."""
    doc_xml = _read_document_xml(file_bytes)
    return _write_answers_impl(doc_xml, file_bytes, answers)


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Detect empty table cells and placeholder text as fillable targets."""
    doc_xml = _read_document_xml(file_bytes)
    return _list_form_fields_impl(doc_xml)
