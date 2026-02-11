"""Word (.docx) handler — extract, validate, build XML, write."""

from __future__ import annotations

from src.models import (
    AnswerPayload,
    BuildInsertionXmlRequest,
    BuildInsertionXmlResponse,
    ExtractStructureResponse,
    FormField,
    LocationSnippet,
    ValidatedLocation,
)

# OOXML namespaces
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Read a .docx and return the full <w:body> XML as a string."""
    raise NotImplementedError


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Match each OOXML snippet against the document body."""
    raise NotImplementedError


def build_insertion_xml(request: BuildInsertionXmlRequest) -> BuildInsertionXmlResponse:
    """Build a <w:r> element inheriting formatting from the target location."""
    raise NotImplementedError


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Insert answers at the specified XPaths and return the modified .docx bytes."""
    raise NotImplementedError


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Detect empty table cells and placeholder text as fillable targets."""
    raise NotImplementedError
