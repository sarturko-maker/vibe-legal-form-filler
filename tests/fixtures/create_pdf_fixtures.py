"""Generate PDF test fixtures with AcroForm widgets using PyMuPDF.

Creates three fixture files:
- simple_form.pdf: text fields, checkbox, dropdown (1 page)
- multi_page_form.pdf: fields across 3 pages
- prefilled_form.pdf: same as simple_form with some fields pre-filled

Run: python tests/fixtures/create_pdf_fixtures.py
"""

from pathlib import Path

import fitz

FIXTURES_DIR = Path(__file__).parent


def _add_label(page: fitz.Page, x: float, y: float, text: str) -> None:
    """Insert a text label on the page."""
    page.insert_text(fitz.Point(x, y), text, fontsize=11)


def _add_text_field(
    page: fitz.Page, name: str, rect: fitz.Rect, value: str = ""
) -> None:
    """Add a text input widget to the page."""
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w.field_name = name
    w.rect = rect
    w.text_fontsize = 10
    if value:
        w.field_value = value
    page.add_widget(w)


def _add_checkbox(
    page: fitz.Page, name: str, rect: fitz.Rect, checked: bool = False
) -> None:
    """Add a checkbox widget to the page."""
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    w.field_name = name
    w.rect = rect
    if checked:
        w.field_value = True
    page.add_widget(w)


def _add_dropdown(
    page: fitz.Page, name: str, rect: fitz.Rect,
    options: list[str], value: str = ""
) -> None:
    """Add a dropdown (combobox) widget to the page."""
    w = fitz.Widget()
    w.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
    w.field_name = name
    w.rect = rect
    w.choice_values = options
    w.text_fontsize = 10
    if value:
        w.field_value = value
    page.add_widget(w)


def create_simple_form() -> None:
    """Create a 1-page form with text fields, checkbox, and dropdown."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Title
    page.insert_text(fitz.Point(50, 50), "Employee Information Form",
                     fontsize=16)

    # Text fields
    _add_label(page, 50, 100, "Full Name:")
    _add_text_field(page, "full_name", fitz.Rect(200, 86, 450, 106))

    _add_label(page, 50, 140, "Email Address:")
    _add_text_field(page, "email", fitz.Rect(200, 126, 450, 146))

    _add_label(page, 50, 180, "Date of Birth:")
    _add_text_field(page, "date_of_birth", fitz.Rect(200, 166, 450, 186))

    # Checkbox
    _add_label(page, 50, 220, "I agree to terms:")
    _add_checkbox(page, "agree_terms", fitz.Rect(200, 208, 218, 226))

    # Dropdown
    _add_label(page, 50, 260, "Department:")
    _add_dropdown(
        page, "department", fitz.Rect(200, 246, 450, 266),
        options=["HR", "Engineering", "Sales", "Finance"],
    )

    doc.save(str(FIXTURES_DIR / "simple_form.pdf"))
    doc.close()
    print("Created simple_form.pdf")


def create_multi_page_form() -> None:
    """Create a 3-page form with fields on each page."""
    doc = fitz.open()

    # Page 1: Personal Information
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text(fitz.Point(50, 50), "Page 1: Personal Information",
                   fontsize=14)

    _add_label(p1, 50, 100, "First Name:")
    _add_text_field(p1, "first_name", fitz.Rect(200, 86, 450, 106))

    _add_label(p1, 50, 140, "Last Name:")
    _add_text_field(p1, "last_name", fitz.Rect(200, 126, 450, 146))

    _add_label(p1, 50, 180, "Phone:")
    _add_text_field(p1, "phone", fitz.Rect(200, 166, 450, 186))

    # Page 2: Employment Details
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text(fitz.Point(50, 50), "Page 2: Employment Details",
                   fontsize=14)

    _add_label(p2, 50, 100, "Position:")
    _add_text_field(p2, "position", fitz.Rect(200, 86, 450, 106))

    _add_label(p2, 50, 140, "Start Date:")
    _add_text_field(p2, "start_date", fitz.Rect(200, 126, 450, 146))

    _add_label(p2, 50, 180, "Full Time:")
    _add_checkbox(p2, "full_time", fitz.Rect(200, 168, 218, 186))

    # Page 3: Declaration
    p3 = doc.new_page(width=612, height=792)
    p3.insert_text(fitz.Point(50, 50), "Page 3: Declaration", fontsize=14)

    _add_label(p3, 50, 100, "Signature:")
    _add_text_field(p3, "signature", fitz.Rect(200, 86, 450, 106))

    _add_label(p3, 50, 140, "Date:")
    _add_text_field(p3, "declaration_date", fitz.Rect(200, 126, 450, 146))

    doc.save(str(FIXTURES_DIR / "multi_page_form.pdf"))
    doc.close()
    print("Created multi_page_form.pdf")


def create_prefilled_form() -> None:
    """Create a form with some fields already filled."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text(fitz.Point(50, 50), "Pre-filled Form", fontsize=16)

    _add_label(page, 50, 100, "Full Name:")
    _add_text_field(page, "full_name", fitz.Rect(200, 86, 450, 106),
                    value="Jane Smith")

    _add_label(page, 50, 140, "Email Address:")
    _add_text_field(page, "email", fitz.Rect(200, 126, 450, 146),
                    value="jane@example.com")

    _add_label(page, 50, 180, "Date of Birth:")
    _add_text_field(page, "date_of_birth", fitz.Rect(200, 166, 450, 186))

    _add_label(page, 50, 220, "I agree to terms:")
    _add_checkbox(page, "agree_terms", fitz.Rect(200, 208, 218, 226),
                  checked=True)

    _add_label(page, 50, 260, "Department:")
    _add_dropdown(
        page, "department", fitz.Rect(200, 246, 450, 266),
        options=["HR", "Engineering", "Sales", "Finance"],
        value="Engineering",
    )

    doc.save(str(FIXTURES_DIR / "prefilled_form.pdf"))
    doc.close()
    print("Created prefilled_form.pdf")


if __name__ == "__main__":
    create_simple_form()
    create_multi_page_form()
    create_prefilled_form()
    print("All PDF fixtures created.")
