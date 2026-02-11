"""Shared validation logic used across handlers."""

from __future__ import annotations

from src.models import FileType


def validate_file_type(file_type: str) -> FileType:
    """Parse and validate a file_type string into a FileType enum."""
    raise NotImplementedError


def validate_file_bytes(file_bytes: bytes, file_type: FileType) -> None:
    """Basic sanity check that file_bytes looks like the claimed file_type.

    Raises ValueError if validation fails.
    """
    raise NotImplementedError
