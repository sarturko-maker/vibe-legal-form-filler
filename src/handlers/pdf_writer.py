"""PDF answer writer — sets widget values using PyMuPDF.

Takes a list of answers (each with a field ID and value) and writes them
into the PDF via the widget API. Returns the modified PDF as bytes.
"""

from __future__ import annotations

import fitz

# Values that should be treated as "checked" for checkboxes
_TRUTHY_VALUES = {"true", "yes", "1", "checked", "on"}


def write_answers(file_bytes: bytes, answers: list[dict]) -> bytes:
    """Write answer values into PDF form fields and return modified bytes.

    file_bytes: raw PDF bytes.
    answers: list of dicts with keys 'field_id' and 'value'.
        field_id is an F-ID (e.g. "F1") assigned by extract_structure_compact.
        value is the plain text value to set.
    Returns the modified PDF as bytes.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    field_index = _build_field_index(doc)

    for answer in answers:
        field_id = answer["field_id"]
        value = answer["value"]

        if field_id not in field_index:
            continue  # skip unknown field IDs silently

        page, widget = field_index[field_id]
        _set_widget_value(page, widget, value)

    result = doc.tobytes()
    doc.close()
    return result


def _build_field_index(
    doc: fitz.Document,
) -> dict[str, tuple[fitz.Page, fitz.Widget]]:
    """Build a mapping from F-ID to (page, widget) for all widgets.

    Iterates pages and widgets in the same deterministic order as
    the indexer, so F-IDs match exactly.
    """
    index: dict[str, tuple[fitz.Page, fitz.Widget]] = {}
    counter = 0

    for page_num in range(doc.page_count):
        page = doc[page_num]
        for widget in page.widgets():
            counter += 1
            field_id = f"F{counter}"
            index[field_id] = (page, widget)

    return index


def _set_widget_value(
    page: fitz.Page, widget: fitz.Widget, value: str
) -> None:
    """Set a widget's value with type-appropriate logic.

    Text: set string directly.
    Checkbox: coerce to bool ("true"/"yes"/"1"/"checked" → True).
    Dropdown/Listbox: set string (no validation against options here).
    Radio: set string directly.
    """
    field_type = widget.field_type

    if field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
        widget.field_value = _coerce_checkbox_value(value)
    else:
        widget.field_value = str(value)

    widget.update()


def _coerce_checkbox_value(value: str) -> bool:
    """Convert a string value to a boolean for checkbox fields.

    "true", "yes", "1", "checked", "on" (case-insensitive) → True.
    Everything else → False.
    """
    return value.strip().lower() in _TRUTHY_VALUES
