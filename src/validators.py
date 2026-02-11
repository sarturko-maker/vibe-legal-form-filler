"""Shared validation logic used across handlers."""

from __future__ import annotations

from src.models import FileType

# Magic bytes for supported file types
_MAGIC_BYTES = {
    FileType.WORD: b"PK",       # ZIP-based (docx is a ZIP archive)
    FileType.EXCEL: b"PK",      # ZIP-based (xlsx is a ZIP archive)
    FileType.PDF: b"%PDF",
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
