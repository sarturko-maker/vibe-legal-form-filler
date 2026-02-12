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

Provides file_type validation, magic-byte checks, path safety, file size limits,
verification summary building, and the resolve_file_input() helper that lets
MCP tools accept either a file_path or base64-encoded bytes.
"""

from __future__ import annotations

import base64
from pathlib import Path

from src.models import FileType

# Maximum file size in bytes (50 MB) — reject before reading into memory
MAX_FILE_SIZE = 50 * 1024 * 1024

# Maximum base64 string length (~67 MB encoded ≈ 50 MB decoded)
MAX_BASE64_LENGTH = 67 * 1024 * 1024

# Maximum number of answers in a single write_answers or verify_output call
MAX_ANSWERS = 10_000

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
            f"file_bytes does not appear to be a valid {file_type.value} file"
        )


def validate_path_safe(file_path: str) -> Path:
    """Resolve a user-supplied path and check for traversal attacks.

    Rejects null bytes and ensures the resolved path is a real filesystem
    location (not /dev/*, /proc/*, /sys/*).  Returns the resolved Path.
    """
    if "\x00" in file_path:
        raise ValueError("Invalid file path")

    resolved = Path(file_path).resolve()

    # Block virtual filesystem paths that could cause hangs or info leaks
    blocked_prefixes = ("/dev/", "/proc/", "/sys/")
    resolved_str = str(resolved)
    if any(resolved_str.startswith(p) for p in blocked_prefixes):
        raise ValueError("Access to system paths is not allowed")

    return resolved


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
    path = validate_path_safe(file_path)
    if not path.is_file():
        raise ValueError("File not found or not accessible")

    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(
            f"File exceeds maximum size ({MAX_FILE_SIZE // (1024 * 1024)} MB)"
        )

    raw = path.read_bytes()

    if file_type:
        ft = validate_file_type(file_type)
    else:
        ext = path.suffix.lower()
        ft = _EXTENSION_TO_FILE_TYPE.get(ext)
        if ft is None:
            supported = ", ".join(_EXTENSION_TO_FILE_TYPE.keys())
            raise ValueError(
                f"Unsupported file extension. Supported: {supported}. "
                f"Pass file_type explicitly."
            )

    validate_file_bytes(raw, ft)
    return raw, ft


def _resolve_from_base64(
    file_bytes_b64: str, file_type: str | None
) -> tuple[bytes, FileType]:
    """Decode base64 bytes and require an explicit file_type."""
    if not file_type:
        raise ValueError(
            "file_type is required when using file_bytes_b64. "
            "Pass file_type='word', 'excel', or 'pdf'."
        )

    if len(file_bytes_b64) > MAX_BASE64_LENGTH:
        raise ValueError(
            f"Base64 input exceeds maximum size "
            f"({MAX_BASE64_LENGTH // (1024 * 1024)} MB encoded)"
        )

    ft = validate_file_type(file_type)
    try:
        raw = base64.b64decode(file_bytes_b64)
    except Exception:
        raise ValueError("Invalid base64 encoding in file_bytes_b64")
    validate_file_bytes(raw, ft)
    return raw, ft
