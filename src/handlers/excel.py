"""Excel (.xlsx) handler — extract, validate, write."""

from __future__ import annotations

from src.models import (
    AnswerPayload,
    ExtractStructureResponse,
    FormField,
    LocationSnippet,
    ValidatedLocation,
)


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Return a JSON representation of sheets, rows, columns, merged cells, and values."""
    raise NotImplementedError


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Confirm cell references exist and are within sheet bounds."""
    raise NotImplementedError


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Write values to cells using openpyxl and return the modified .xlsx bytes."""
    raise NotImplementedError


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Detect Q/A column patterns and empty cells adjacent to question text."""
    raise NotImplementedError
