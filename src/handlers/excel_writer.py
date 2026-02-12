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

"""Excel (.xlsx) answer writer — writes cell values using openpyxl.

Takes a list of answers (each with a cell ID and value) and writes them
into the workbook. Returns the modified .xlsx as bytes.
"""

from __future__ import annotations

import re
from io import BytesIO

import openpyxl

CELL_ID_RE = re.compile(r"^S(\d+)-R(\d+)-C(\d+)$")


def write_answers(
    file_bytes: bytes, answers: list[dict[str, str]]
) -> bytes:
    """Write answer values into cells and return the modified .xlsx bytes.

    file_bytes: raw .xlsx file bytes.
    answers: list of dicts with keys 'pair_id', 'cell_id', 'value'.
    Returns the modified workbook as bytes.
    """
    wb = openpyxl.load_workbook(BytesIO(file_bytes))

    for answer in answers:
        cell_id = answer["cell_id"]
        value = answer["value"]
        sheet_idx, row, col = _parse_cell_id(cell_id)
        ws = _get_worksheet(wb, sheet_idx)
        ws.cell(row=row, column=col, value=value)

    return _save_workbook(wb)


def _parse_cell_id(cell_id: str) -> tuple[int, int, int]:
    """Parse a cell ID like 'S1-R2-C3' into (sheet_index, row, column).

    All values are 1-indexed.
    Raises ValueError if the format is invalid.
    """
    match = CELL_ID_RE.match(cell_id)
    if not match:
        raise ValueError(
            f"Invalid cell ID format: {cell_id!r}. "
            f"Expected S{{sheet}}-R{{row}}-C{{col}} (e.g. S1-R2-C3)"
        )
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _get_worksheet(
    wb: openpyxl.Workbook, sheet_idx: int
) -> openpyxl.worksheet.worksheet.Worksheet:
    """Get a worksheet by 1-indexed sheet number.

    Raises ValueError if the sheet index is out of range.
    """
    if sheet_idx < 1 or sheet_idx > len(wb.worksheets):
        raise ValueError(
            f"Sheet index {sheet_idx} out of range. "
            f"Workbook has {len(wb.worksheets)} sheet(s)."
        )
    return wb.worksheets[sheet_idx - 1]


def _save_workbook(wb: openpyxl.Workbook) -> bytes:
    """Save a workbook to bytes."""
    buf = BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()
