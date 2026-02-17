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

"""Word (.docx) write operations — insert answers into documents.

Handles the write step of the pipeline: locate target elements by XPath,
insert content (replace, append, or replace placeholder), and repackage
the modified XML back into a valid .docx ZIP archive.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO

from lxml import etree

from src.models import AnswerPayload, InsertionMode
from src.xml_utils import (
    NAMESPACES,
    SECURE_PARSER,
    build_run_xml,
    extract_formatting_from_element,
    parse_snippet,
)

WORD_NAMESPACE_URI = NAMESPACES["w"]

# Allowed XPath pattern: positional steps using OOXML element names only
_XPATH_SAFE_RE = re.compile(
    r"^\.(/w:(body|tbl|tr|tc|p|r|sdt|sdtContent)(\[\d+\])?)+$"
)


def _replace_content(target: etree._Element, insertion_xml: str) -> None:
    """Clear existing content in target and insert new XML.

    Preserves w:pPr/w:tcPr property elements. When the target is a w:tc,
    wraps bare w:r elements in a w:p (OOXML requires runs inside paragraphs).
    """
    preserve_tags = {
        f"{{{WORD_NAMESPACE_URI}}}pPr",
        f"{{{WORD_NAMESPACE_URI}}}tcPr",
    }
    for child in list(target):
        if child.tag not in preserve_tags:
            target.remove(child)
    target.text = None

    new_elem = parse_snippet(insertion_xml)
    if new_elem is None:
        return

    is_table_cell = target.tag == f"{{{WORD_NAMESPACE_URI}}}tc"
    is_run = new_elem.tag == f"{{{WORD_NAMESPACE_URI}}}r"

    if is_table_cell and is_run:
        para = etree.Element(f"{{{WORD_NAMESPACE_URI}}}p")
        para.append(new_elem)
        target.append(para)
    else:
        target.append(new_elem)


def _append_content(target: etree._Element, insertion_xml: str) -> None:
    """Append new content after existing content in target."""
    new_elem = parse_snippet(insertion_xml)
    if new_elem is not None:
        target.append(new_elem)


def _replace_placeholder(
    target: etree._Element, insertion_xml: str, placeholder: str | None = None
) -> None:
    """Find placeholder text in the target and replace it.

    Without a specific placeholder, matches: [Enter ...], ___ (3+ underscores).
    """
    placeholder_patterns = [
        re.compile(r"\[Enter[^\]]*\]"),
        re.compile(r"_{3,}"),
    ]

    new_elem = parse_snippet(insertion_xml)
    if new_elem is None:
        return

    new_text_elem = new_elem.find(f".//{{{WORD_NAMESPACE_URI}}}t")
    new_text = new_text_elem.text if new_text_elem is not None else ""

    for t_elem in target.iter(f"{{{WORD_NAMESPACE_URI}}}t"):
        if t_elem.text is None:
            continue

        if placeholder:
            if placeholder in t_elem.text:
                t_elem.text = t_elem.text.replace(placeholder, new_text)
                return
        else:
            for pattern in placeholder_patterns:
                match = pattern.search(t_elem.text)
                if match:
                    t_elem.text = pattern.sub(new_text, t_elem.text)
                    return


def _repackage_docx_zip(file_bytes: bytes, modified_xml: bytes) -> bytes:
    """Rewrite a .docx ZIP, replacing word/document.xml with modified_xml."""
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf_in:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                if item.filename == "word/document.xml":
                    zf_out.writestr(item, modified_xml)
                else:
                    zf_out.writestr(item, zf_in.read(item.filename))
    return output.getvalue()


def _validate_xpath(xpath: str) -> None:
    """Reject XPaths that don't match the expected positional-steps pattern."""
    if not _XPATH_SAFE_RE.match(xpath):
        raise ValueError(f"XPath does not match expected pattern: {xpath!r}")


def _build_insertion_xml_for_answer_text(
    target: etree._Element, answer_text: str
) -> str:
    """Build insertion OOXML from plain text, inheriting formatting from target.

    This is the fast path: the server builds the same XML that the
    build_insertion_xml MCP tool would produce, without an extra round-trip.
    """
    formatting = extract_formatting_from_element(target)
    return build_run_xml(answer_text, formatting)


def _apply_answer(body: etree._Element, answer: AnswerPayload) -> None:
    """Locate a single answer's target by XPath and insert its content."""
    _validate_xpath(answer.xpath)
    matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
    if not matched:
        raise ValueError(
            f"XPath '{answer.xpath}' for pair_id '{answer.pair_id}' "
            f"did not match any element in the document"
        )
    target = matched[0]

    # Fast path: build insertion XML from answer_text when provided
    if answer.answer_text is not None and answer.answer_text.strip():
        insertion_xml = _build_insertion_xml_for_answer_text(
            target, answer.answer_text
        )
    else:
        insertion_xml = answer.insertion_xml

    if answer.mode == InsertionMode.REPLACE_CONTENT:
        _replace_content(target, insertion_xml)
    elif answer.mode == InsertionMode.APPEND:
        _append_content(target, insertion_xml)
    elif answer.mode == InsertionMode.REPLACE_PLACEHOLDER:
        _replace_placeholder(target, insertion_xml)


def write_answers(
    doc_xml: bytes, file_bytes: bytes, answers: list[AnswerPayload]
) -> bytes:
    """Insert answers into the document XML and return modified .docx bytes.

    doc_xml: raw word/document.xml bytes from the .docx archive.
    file_bytes: the original .docx file bytes (for repackaging).
    answers: list of answer payloads with XPaths and insertion XML.
    """
    root = etree.fromstring(doc_xml, SECURE_PARSER)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")

    for answer in answers:
        _apply_answer(body, answer)

    modified_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                  standalone=True)
    return _repackage_docx_zip(file_bytes, modified_xml)
