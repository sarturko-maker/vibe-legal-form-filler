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

"""Pair ID resolution and cross-check logic.

Resolves pair_ids to xpaths via re-extraction of the compact structure.
Called from tool_errors.py during payload construction when xpath is not
provided. The resolution reuses the same extract_structure_compact()
functions used by the extraction tools.

Public functions:
    resolve_pair_ids  -- resolve pair_ids to xpaths for any file type
    cross_check_xpaths -- compare agent xpaths against resolved xpaths
    resolve_if_needed -- resolve and cross-check in one call (used by tool_errors)
    infer_relaxed_file_type -- guess Excel vs PDF from pair_id format
"""

from __future__ import annotations

from src.models import FileType


def resolve_pair_ids(
    file_bytes: bytes,
    file_type: FileType,
    pair_ids: list[str],
) -> dict[str, str]:
    """Resolve pair_ids to xpaths via compact re-extraction.

    file_bytes: raw document bytes (.docx, .xlsx, or .pdf).
    file_type: which handler to use for extraction.
    pair_ids: list of element IDs to look up.

    Returns a dict mapping pair_id -> xpath. Pair_ids not found in the
    document are omitted (caller must check for missing entries).
    """
    if file_type == FileType.WORD:
        from src.handlers.word_indexer import extract_structure_compact
    elif file_type == FileType.EXCEL:
        from src.handlers.excel_indexer import extract_structure_compact
    elif file_type == FileType.PDF:
        from src.handlers.pdf_indexer import extract_structure_compact
    else:
        return {}

    compact = extract_structure_compact(file_bytes)
    return {
        pid: compact.id_to_xpath[pid]
        for pid in pair_ids
        if pid in compact.id_to_xpath
    }


def resolve_if_needed(
    answer_dicts: list[dict],
    ft: FileType,
    file_bytes: bytes | None,
    is_provided_fn: callable,
) -> tuple[dict[str, str], list[str]]:
    """Resolve pair_ids and cross-check xpaths when needed.

    answer_dicts: raw answer dicts from the agent.
    ft: FileType for the current document.
    file_bytes: raw document bytes (None skips resolution).
    is_provided_fn: callable to check if a string field has content.

    Returns (resolved_map, warnings). If no resolution is needed or
    file_bytes is None, returns empty dict and empty list.
    """
    needs_resolution = any(
        not a.get("xpath") and not a.get("cell_id") and not a.get("field_id")
        and is_provided_fn(a.get("answer_text"))
        for a in answer_dicts
    )
    needs_cross_check = any(
        (a.get("xpath") or a.get("cell_id") or a.get("field_id"))
        and a.get("pair_id")
        for a in answer_dicts
    )

    if not (needs_resolution or needs_cross_check) or file_bytes is None:
        return {}, []

    pair_ids = [a["pair_id"] for a in answer_dicts if a.get("pair_id")]
    resolved = resolve_pair_ids(file_bytes, ft, pair_ids)
    warnings = cross_check_xpaths(answer_dicts, resolved)
    return resolved, warnings


def infer_relaxed_file_type(answer_dicts: list[dict]) -> FileType:
    """Infer FileType from pair_id format on the relaxed path.

    S-prefix IDs are Excel, F-prefix IDs are PDF. Defaults to Excel.
    """
    for a in answer_dicts:
        pid = a.get("pair_id", "")
        if pid.startswith("F"):
            return FileType.PDF
        if pid.startswith("S"):
            return FileType.EXCEL
    return FileType.EXCEL


def cross_check_xpaths(
    answers: list[dict],
    resolved: dict[str, str],
) -> list[str]:
    """Compare agent-provided xpaths against resolved xpaths.

    answers: list of answer dicts, each with optional 'pair_id' and 'xpath'.
    resolved: dict mapping pair_id -> xpath from resolve_pair_ids.

    Returns a list of warning strings for mismatches. Empty list if no
    mismatches or if either side is missing. pair_id resolution takes
    precedence (warnings only, not errors).
    """
    warnings: list[str] = []
    for answer in answers:
        pair_id = answer.get("pair_id", "")
        agent_xpath = answer.get("xpath", "")
        resolved_xpath = resolved.get(pair_id, "")
        if agent_xpath and resolved_xpath and agent_xpath != resolved_xpath:
            warnings.append(
                f"pair_id '{pair_id}': agent xpath '{agent_xpath}' "
                f"differs from resolved xpath '{resolved_xpath}' "
                f"-- using resolved (pair_id is authority)"
            )
    return warnings
