"""PDF handler (fillable forms only) — extract, validate, write."""

from __future__ import annotations

from src.models import (
    AnswerPayload,
    ExtractStructureResponse,
    FormField,
    LocationSnippet,
    ValidatedLocation,
)


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Return a list of fillable field names, types, and current values."""
    raise NotImplementedError


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Confirm field names exist in the PDF form."""
    raise NotImplementedError


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Fill fields by name and return the modified PDF bytes."""
    raise NotImplementedError


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Return all named form fields (same as extract_structure for PDF)."""
    raise NotImplementedError
