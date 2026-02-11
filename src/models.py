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


class LocationStatus(str, Enum):
    MATCHED = "matched"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


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
    xpath: str            # Word/Excel/PDF target reference
    insertion_xml: str    # pre-built XML (Word) or plain value (Excel/PDF)
    mode: InsertionMode


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
