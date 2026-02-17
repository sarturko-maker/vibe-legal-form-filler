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

"""Word (.docx) dry-run preview — resolve answer targets without modifying.

Given answers and file bytes, resolves each XPath and returns a preview
showing current cell content alongside what would be written. The agent
reviews the preview and can catch 'right answer, wrong cell' errors
before committing.
"""

from __future__ import annotations

from lxml import etree

from src.models import AnswerPayload
from src.xml_utils import NAMESPACES, SECURE_PARSER

from src.handlers.word_element_analysis import get_text
from src.handlers.word_parser import read_document_xml


def preview_answers(
    file_bytes: bytes, answers: list[AnswerPayload]
) -> list[dict]:
    """Resolve each answer's XPath and return a preview without writing.

    Returns a list of preview dicts, one per answer, with:
      - pair_id: the answer's pair_id
      - xpath: the target XPath
      - current_text: existing text at the target location
      - would_write: what the answer would insert (answer_text or
        'pre-built XML' for insertion_xml)
      - status: 'ok' or 'warning' (if target already has content)
    """
    doc_xml = read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml, SECURE_PARSER)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")

    previews: list[dict] = []
    for answer in answers:
        previews.append(_preview_single(body, answer))
    return previews


def _preview_single(body: etree._Element, answer: AnswerPayload) -> dict:
    """Build a preview dict for a single answer."""
    matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
    if not matched:
        return {
            "pair_id": answer.pair_id,
            "xpath": answer.xpath,
            "current_text": "",
            "would_write": _describe_write(answer),
            "status": "error",
            "message": f"XPath did not match any element",
        }

    target = matched[0]
    current = get_text(target)
    would_write = _describe_write(answer)
    has_content = bool(current.strip())

    result = {
        "pair_id": answer.pair_id,
        "xpath": answer.xpath,
        "current_text": current,
        "would_write": would_write,
        "mode": answer.mode.value,
        "status": "warning" if has_content else "ok",
    }
    if has_content:
        result["message"] = (
            f"Target already contains: '{current[:60]}'"
            f"{'...' if len(current) > 60 else ''}"
        )
    return result


def _describe_write(answer: AnswerPayload) -> str:
    """Describe what would be written for a single answer."""
    if answer.answer_text is not None and answer.answer_text.strip():
        return answer.answer_text
    if answer.insertion_xml:
        return f"[pre-built XML: {len(answer.insertion_xml)} chars]"
    return "[empty]"
