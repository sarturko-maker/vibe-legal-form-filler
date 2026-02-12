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

"""Shared validation logic used across handlers.

Provides file_type validation, magic-byte checks, and the resolve_file_input()
helper that lets MCP tools accept either a file_path or base64-encoded bytes.
"""

from __future__ import annotations

import base64
from pathlib import Path

from src.models import FileType

# Magic bytes for supported file types
_MAGIC_BYTES = {
    FileType.WORD: b"PK",       # ZIP-based (docx is a ZIP archive)
    FileType.EXCEL: b"PK",      # ZIP-based (xlsx is a ZIP archive)
    FileType.PDF: b"%PDF",
}

# Map file extensions to FileType for auto-inference
_EXTENSION_TO_FILE_TYPE: dict[str, FileType] = {
    ".docx": FileType.WORD,
    ".xlsx": FileType.EXCEL,
    ".pdf": FileType.PDF,
}


def validate_file_type(file_type: str) -> FileType:
    """Parse and validate a file_type string into a FileType enum."""
    try:
        return FileType(file_type.lower())
    except ValueError:
        valid = ", ".join(ft.value for ft in FileType)
        raise ValueError(f"Invalid file_type '{file_type}'. Must be one of: {valid}")


def validate_file_bytes(file_bytes: bytes, file_type: FileType) -> None:
    """Basic sanity check that file_bytes looks like the claimed file_type.

    Raises ValueError if validation fails.
    """
    if not file_bytes:
        raise ValueError("file_bytes is empty")

    magic = _MAGIC_BYTES.get(file_type)
    if magic and not file_bytes[:len(magic)].startswith(magic):
        raise ValueError(
            f"file_bytes does not appear to be a valid {file_type.value} file "
            f"(expected magic bytes {magic!r}, got {file_bytes[:8]!r})"
        )


def resolve_file_input(
    file_bytes_b64: str | None,
    file_type: str | None,
    file_path: str | None,
) -> tuple[bytes, FileType]:
    """Resolve file input from either a disk path or base64-encoded bytes.

    When file_path is provided, reads the file from disk and infers file_type
    from the extension (.docx→word, .xlsx→excel, .pdf→pdf).  An explicit
    file_type overrides the inferred value.

    When file_bytes_b64 is provided instead, decodes the base64 string.
    file_type is required in this case.

    Returns (raw_bytes, FileType).  Raises ValueError on bad input.
    """
    if file_path:
        return _resolve_from_path(file_path, file_type)

    if file_bytes_b64:
        return _resolve_from_base64(file_bytes_b64, file_type)

    raise ValueError(
        "Provide either file_path or file_bytes_b64. Neither was supplied."
    )


def _resolve_from_path(file_path: str, file_type: str | None) -> tuple[bytes, FileType]:
    """Read bytes from disk and infer or validate file_type."""
    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"File not found: {file_path}")

    raw = path.read_bytes()

    if file_type:
        ft = validate_file_type(file_type)
    else:
        ext = path.suffix.lower()
        ft = _EXTENSION_TO_FILE_TYPE.get(ext)
        if ft is None:
            supported = ", ".join(_EXTENSION_TO_FILE_TYPE.keys())
            raise ValueError(
                f"Cannot infer file_type from extension '{ext}'. "
                f"Supported: {supported}. Pass file_type explicitly."
            )

    validate_file_bytes(raw, ft)
    return raw, ft


def count_confidence(expected_answers: list) -> dict:
    """Count confidence levels across expected answers and build a summary note.

    Works with any list of objects that have a .confidence attribute
    (e.g. ExpectedAnswer). Returns a dict with confidence_known,
    confidence_uncertain, confidence_unknown, and confidence_note.
    """
    from src.models import Confidence

    known = sum(1 for a in expected_answers if a.confidence == Confidence.KNOWN)
    uncertain = sum(1 for a in expected_answers if a.confidence == Confidence.UNCERTAIN)
    unknown = sum(1 for a in expected_answers if a.confidence == Confidence.UNKNOWN)

    parts = []
    if known:
        parts.append(f"{known} known")
    if uncertain:
        parts.append(f"{uncertain} uncertain")
    if unknown:
        parts.append(f"{unknown} unknown")
    note = ", ".join(parts)
    if uncertain or unknown:
        note += " — manual review needed"

    return {
        "confidence_known": known,
        "confidence_uncertain": uncertain,
        "confidence_unknown": unknown,
        "confidence_note": note,
    }


def _resolve_from_base64(
    file_bytes_b64: str, file_type: str | None
) -> tuple[bytes, FileType]:
    """Decode base64 bytes and require an explicit file_type."""
    if not file_type:
        raise ValueError(
            "file_type is required when using file_bytes_b64. "
            "Pass file_type='word', 'excel', or 'pdf'."
        )

    ft = validate_file_type(file_type)
    raw = base64.b64decode(file_bytes_b64)
    validate_file_bytes(raw, ft)
    return raw, ft
