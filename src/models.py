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

"""Pydantic models for all MCP tool inputs and outputs."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


# ── Enums ──────────────────────────────────────────────────────────────────────

class FileType(str, Enum):
    WORD = "word"
    EXCEL = "excel"
    PDF = "pdf"


class AnswerType(str, Enum):
    PLAIN_TEXT = "plain_text"
    STRUCTURED = "structured"


class InsertionMode(str, Enum):
    REPLACE_CONTENT = "replace_content"
    APPEND = "append"
    REPLACE_PLACEHOLDER = "replace_placeholder"


class Confidence(str, Enum):
    KNOWN = "known"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class LocationStatus(str, Enum):
    MATCHED = "matched"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


# ── extract_structure_compact ──────────────────────────────────────────────────

class CompactStructureResponse(BaseModel):
    """Compact indexed representation of document structure.

    compact_text: human-readable indexed representation with element IDs.
    id_to_xpath: mapping from every element ID to its XPath in the document.
    complex_elements: list of element IDs flagged as containing complex OOXML.
    """
    compact_text: str
    id_to_xpath: dict[str, str]
    complex_elements: list[str]


# ── extract_structure ──────────────────────────────────────────────────────────

class ExtractStructureRequest(BaseModel):
    file_bytes: bytes
    file_type: FileType


class ExtractStructureResponse(BaseModel):
    """Union-style response: exactly one of the fields will be populated."""
    body_xml: str | None = None          # Word
    sheets_json: list[dict] | None = None  # Excel
    fields: list[FormField] | None = None  # PDF


# ── validate_locations ─────────────────────────────────────────────────────────

class LocationSnippet(BaseModel):
    pair_id: str
    snippet: str  # OOXML snippet (Word), cell ref (Excel), field name (PDF)


class ValidatedLocation(BaseModel):
    pair_id: str
    status: LocationStatus
    xpath: str | None = None
    context: str | None = None


class ValidateLocationsRequest(BaseModel):
    file_bytes: bytes
    file_type: FileType
    locations: list[LocationSnippet]


class ValidateLocationsResponse(BaseModel):
    validated: list[ValidatedLocation]


# ── build_insertion_xml ────────────────────────────────────────────────────────

class BuildInsertionXmlRequest(BaseModel):
    answer_text: str
    target_context_xml: str
    answer_type: AnswerType


class BuildInsertionXmlResponse(BaseModel):
    insertion_xml: str
    valid: bool
    error: str | None = None


# ── write_answers ──────────────────────────────────────────────────────────────

class AnswerPayload(BaseModel):
    pair_id: str
    xpath: str                          # Word/Excel/PDF target reference
    insertion_xml: str | None = None    # pre-built XML (Word) or plain value (Excel/PDF)
    answer_text: str | None = None      # plain text answer (fast path, Phase 6)
    mode: InsertionMode
    confidence: Confidence = Confidence.KNOWN


class WriteAnswersRequest(BaseModel):
    file_bytes: bytes
    file_type: FileType
    answers: list[AnswerPayload]


class WriteAnswersResponse(BaseModel):
    file_bytes: bytes


# ── list_form_fields ──────────────────────────────────────────────────────────

class FormField(BaseModel):
    field_id: str
    label: str
    field_type: str
    current_value: str | None = None


class ListFormFieldsRequest(BaseModel):
    file_bytes: bytes
    file_type: FileType


class ListFormFieldsResponse(BaseModel):
    fields: list[FormField]


# ── verify_output ─────────────────────────────────────────────────────────────

class ContentStatus(str, Enum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    MISSING = "missing"


class ExpectedAnswer(BaseModel):
    pair_id: str
    xpath: str
    expected_text: str
    confidence: Confidence = Confidence.KNOWN


class ContentResult(BaseModel):
    pair_id: str
    status: ContentStatus
    expected: str
    actual: str


class VerificationSummary(BaseModel):
    total: int
    matched: int
    mismatched: int
    missing: int
    structural_issues: int
    confidence_known: int = 0
    confidence_uncertain: int = 0
    confidence_unknown: int = 0
    confidence_note: str = ""


class VerificationReport(BaseModel):
    structural_issues: list[str]
    content_results: list[ContentResult]
    summary: VerificationSummary
