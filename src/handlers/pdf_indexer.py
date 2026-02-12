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

"""Compact extraction — walks PDF pages and builds an indexed field inventory.

Assigns sequential field IDs (F1, F2, ...) in page order. Extracts nearby
text by expanding widget bounding boxes. Detects field types (text, checkbox,
dropdown, radio, listbox). Returns a CompactStructureResponse.
"""

from __future__ import annotations

import fitz

from src.models import CompactStructureResponse

# PyMuPDF widget type constants → human-readable names
_WIDGET_TYPE_NAMES: dict[int, str] = {
    fitz.PDF_WIDGET_TYPE_TEXT: "text",
    fitz.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
    fitz.PDF_WIDGET_TYPE_COMBOBOX: "dropdown",
    fitz.PDF_WIDGET_TYPE_LISTBOX: "listbox",
    fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
}

# How far (in points) to expand the widget rect when grabbing nearby text
_CONTEXT_EXPAND = (-200, -30, 200, 30)


def extract_structure_compact(file_bytes: bytes) -> CompactStructureResponse:
    """Walk all pages, index every AcroForm widget, and return compact output.

    file_bytes: raw PDF bytes.
    Returns CompactStructureResponse with compact_text and id_to_xpath
    (F-ID → native field name mapping).
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    fields = _collect_fields(doc)
    doc.close()

    if not fields:
        return _empty_response()

    lines = _build_compact_lines(fields)
    id_to_xpath = {f["field_id"]: f["native_name"] for f in fields}

    return CompactStructureResponse(
        compact_text="\n".join(lines),
        id_to_xpath=id_to_xpath,
        complex_elements=[],
    )


def _collect_fields(doc: fitz.Document) -> list[dict]:
    """Iterate all pages and widgets, assign F-IDs, extract context."""
    fields: list[dict] = []
    counter = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        for widget in page.widgets():
            counter += 1
            field_id = f"F{counter}"
            fields.append({
                "field_id": field_id,
                "native_name": widget.field_name or f"unnamed_{counter}",
                "page": page_num + 1,
                "field_type": _map_widget_type(widget.field_type),
                "value": _get_current_value(widget),
                "options": _get_field_options(widget),
                "context": _get_nearby_text(page, widget),
                "read_only": bool(widget.field_flags & 1),
            })

    return fields


def _map_widget_type(widget_type: int) -> str:
    """Convert PyMuPDF widget type constant to a human-readable string."""
    return _WIDGET_TYPE_NAMES.get(widget_type, f"unknown({widget_type})")


def _get_current_value(widget: fitz.Widget) -> str:
    """Get the current value of a widget as a string."""
    if widget.field_value is None:
        return ""
    return str(widget.field_value)


def _get_field_options(widget: fitz.Widget) -> list[str]:
    """Get the choice options for dropdown/listbox/radio widgets."""
    if widget.choice_values:
        return list(widget.choice_values)
    return []


def _get_nearby_text(page: fitz.Page, widget: fitz.Widget) -> str:
    """Extract text near the widget by expanding its bounding box.

    Expands the widget rect by _CONTEXT_EXPAND, clips to page bounds,
    then grabs all text in that region. Returns cleaned, single-line text.
    """
    expanded = widget.rect + _CONTEXT_EXPAND
    expanded &= page.rect  # clip to page bounds
    text = page.get_text("text", clip=expanded).strip()
    # Collapse whitespace and newlines into pipe-separated tokens
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    return " | ".join(parts)


def _build_compact_lines(fields: list[dict]) -> list[str]:
    """Build human-readable compact_text lines from collected field data."""
    lines: list[str] = []
    pages = sorted(set(f["page"] for f in fields))
    total = len(fields)
    page_count = len(pages)

    lines.append(
        f"=== PDF Form: {total} field{'s' if total != 1 else ''} "
        f"across {page_count} page{'s' if page_count != 1 else ''} ==="
    )

    for page_num in pages:
        lines.append("")
        lines.append(f"Page {page_num}:")
        page_fields = [f for f in fields if f["page"] == page_num]
        for field in page_fields:
            lines.append(_format_field_line(field))
            if field["context"]:
                lines.append(f"    Context: {field['context']}")

    return lines


def _format_field_line(field: dict) -> str:
    """Format a single field as a compact line.

    Example: [F1] "employee_name" (text) — empty
    Example: [F3] "dept" (dropdown, options: HR | Sales) — "HR"
    """
    fid = field["field_id"]
    name = field["native_name"]
    ftype = field["field_type"]
    value = field["value"]
    options = field["options"]
    read_only = field.get("read_only", False)

    type_str = ftype
    if options:
        type_str += f", options: {' | '.join(options)}"

    value_str = _describe_value(ftype, value)
    ro_str = " [read-only]" if read_only else ""

    return f'[{fid}] "{name}" ({type_str}) — {value_str}{ro_str}'


def _describe_value(field_type: str, value: str) -> str:
    """Describe the current value in a human-readable way."""
    if field_type == "checkbox":
        return "checked" if value not in ("", "Off", "No") else "unchecked"
    if not value or value == "Off":
        return "empty"
    return f'"{value}"'


def _empty_response() -> CompactStructureResponse:
    """Return a response indicating no fillable fields were found."""
    msg = (
        "No fillable form fields found. "
        "This PDF may be a flat/scanned document."
    )
    return CompactStructureResponse(
        compact_text=msg,
        id_to_xpath={},
        complex_elements=[],
    )
