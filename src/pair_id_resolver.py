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
