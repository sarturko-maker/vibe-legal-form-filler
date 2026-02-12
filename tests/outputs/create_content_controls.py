"""Script to create a Word .docx with w:sdt content controls (dropdown + date picker).

Creates edge_content_controls.docx in the same directory. The document contains:
- A paragraph: "Form with content controls"
- A 2x2 table:
    Row 1: "Select option:" | <w:sdt dropdown>
    Row 2: "Select date:"   | <w:sdt date picker>
"""

import zipfile
from io import BytesIO
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"

NSMAP = {"w": W, "r": R, "mc": MC}


def _el(tag, nsmap=None, **attribs):
    """Create an element with Clark notation for the w: namespace."""
    ns_attribs = {}
    for k, v in attribs.items():
        if ":" in k:
            prefix, local = k.split(":", 1)
            if prefix == "w":
                ns_attribs[f"{{{W}}}{local}"] = v
            else:
                ns_attribs[k] = v
        else:
            ns_attribs[k] = v
    return etree.SubElement(
        etree.Element("_dummy"),
        f"{{{W}}}{tag}",
        nsmap=nsmap,
        attrib=ns_attribs,
    )


def make_run(text):
    """Create a w:r > w:t element with the given text."""
    r = etree.Element(f"{{{W}}}r")
    t = etree.SubElement(r, f"{{{W}}}t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def make_paragraph(text=None, runs=None):
    """Create a w:p element with optional text or child runs."""
    p = etree.Element(f"{{{W}}}p")
    if text is not None:
        p.append(make_run(text))
    if runs:
        for r in runs:
            p.append(r)
    return p


def make_sdt_dropdown():
    """Create a w:sdt structured document tag with a dropdown list."""
    sdt = etree.Element(f"{{{W}}}sdt")

    # sdtPr
    sdt_pr = etree.SubElement(sdt, f"{{{W}}}sdtPr")
    alias = etree.SubElement(sdt_pr, f"{{{W}}}alias")
    alias.set(f"{{{W}}}val", "Options")
    tag = etree.SubElement(sdt_pr, f"{{{W}}}tag")
    tag.set(f"{{{W}}}val", "dropdown1")

    dropdown = etree.SubElement(sdt_pr, f"{{{W}}}dropDownList")
    item1 = etree.SubElement(dropdown, f"{{{W}}}listItem")
    item1.set(f"{{{W}}}displayText", "Option A")
    item1.set(f"{{{W}}}value", "a")
    item2 = etree.SubElement(dropdown, f"{{{W}}}listItem")
    item2.set(f"{{{W}}}displayText", "Option B")
    item2.set(f"{{{W}}}value", "b")
    item3 = etree.SubElement(dropdown, f"{{{W}}}listItem")
    item3.set(f"{{{W}}}displayText", "Option C")
    item3.set(f"{{{W}}}value", "c")

    # sdtContent
    sdt_content = etree.SubElement(sdt, f"{{{W}}}sdtContent")
    r = etree.SubElement(sdt_content, f"{{{W}}}r")
    t = etree.SubElement(r, f"{{{W}}}t")
    t.text = "Select..."

    return sdt


def make_sdt_date_picker():
    """Create a w:sdt structured document tag with a date picker."""
    sdt = etree.Element(f"{{{W}}}sdt")

    # sdtPr
    sdt_pr = etree.SubElement(sdt, f"{{{W}}}sdtPr")
    alias = etree.SubElement(sdt_pr, f"{{{W}}}alias")
    alias.set(f"{{{W}}}val", "Date")
    tag = etree.SubElement(sdt_pr, f"{{{W}}}tag")
    tag.set(f"{{{W}}}val", "datepicker1")

    date_el = etree.SubElement(sdt_pr, f"{{{W}}}date")
    date_el.set(f"{{{W}}}fullDate", "2025-01-01T00:00:00Z")
    date_format = etree.SubElement(date_el, f"{{{W}}}dateFormat")
    date_format.set(f"{{{W}}}val", "MM/dd/yyyy")
    lid = etree.SubElement(date_el, f"{{{W}}}lid")
    lid.set(f"{{{W}}}val", "en-US")
    storage = etree.SubElement(date_el, f"{{{W}}}storeMappedDataAs")
    storage.set(f"{{{W}}}val", "dateTime")

    # sdtContent
    sdt_content = etree.SubElement(sdt, f"{{{W}}}sdtContent")
    r = etree.SubElement(sdt_content, f"{{{W}}}r")
    t = etree.SubElement(r, f"{{{W}}}t")
    t.text = "Click to select date..."

    return sdt


def make_table_cell(content):
    """Create a w:tc with either text or an element (like w:sdt) inside a paragraph."""
    tc = etree.Element(f"{{{W}}}tc")
    # cell properties
    tc_pr = etree.SubElement(tc, f"{{{W}}}tcPr")
    tc_w = etree.SubElement(tc_pr, f"{{{W}}}tcW")
    tc_w.set(f"{{{W}}}w", "4500")
    tc_w.set(f"{{{W}}}type", "dxa")

    if isinstance(content, str):
        # Simple text cell
        p = make_paragraph(content)
        tc.append(p)
    else:
        # Element (w:sdt) inside a paragraph
        p = etree.Element(f"{{{W}}}p")
        p.append(content)
        tc.append(p)

    return tc


def make_table_row(cells):
    """Create a w:tr from a list of cell contents."""
    tr = etree.Element(f"{{{W}}}tr")
    for cell_content in cells:
        tr.append(make_table_cell(cell_content))
    return tr


def build_document_xml():
    """Build the complete document.xml with content controls."""
    # Root document element
    doc = etree.Element(
        f"{{{W}}}document",
        nsmap=NSMAP,
    )
    body = etree.SubElement(doc, f"{{{W}}}body")

    # Paragraph: "Form with content controls"
    body.append(make_paragraph("Form with content controls"))

    # Table: 2 rows x 2 columns
    tbl = etree.SubElement(body, f"{{{W}}}tbl")

    # Table properties
    tbl_pr = etree.SubElement(tbl, f"{{{W}}}tblPr")
    tbl_w = etree.SubElement(tbl_pr, f"{{{W}}}tblW")
    tbl_w.set(f"{{{W}}}w", "9000")
    tbl_w.set(f"{{{W}}}type", "dxa")
    tbl_borders = etree.SubElement(tbl_pr, f"{{{W}}}tblBorders")
    for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = etree.SubElement(tbl_borders, f"{{{W}}}{border_name}")
        b.set(f"{{{W}}}val", "single")
        b.set(f"{{{W}}}sz", "4")
        b.set(f"{{{W}}}space", "0")
        b.set(f"{{{W}}}color", "000000")

    # Table grid
    tbl_grid = etree.SubElement(tbl, f"{{{W}}}tblGrid")
    for _ in range(2):
        col = etree.SubElement(tbl_grid, f"{{{W}}}gridCol")
        col.set(f"{{{W}}}w", "4500")

    # Row 1: "Select option:" | dropdown content control
    tbl.append(make_table_row(["Select option:", make_sdt_dropdown()]))

    # Row 2: "Select date:" | date picker content control
    tbl.append(make_table_row(["Select date:", make_sdt_date_picker()]))

    # Trailing section properties paragraph (required by some Word versions)
    sect_p = etree.SubElement(body, f"{{{W}}}p")
    ppr = etree.SubElement(sect_p, f"{{{W}}}pPr")
    sect_pr = etree.SubElement(ppr, f"{{{W}}}sectPr")
    pg_sz = etree.SubElement(sect_pr, f"{{{W}}}pgSz")
    pg_sz.set(f"{{{W}}}w", "12240")
    pg_sz.set(f"{{{W}}}h", "15840")

    return etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone=True)


def build_docx():
    """Package document.xml into a minimal .docx (ZIP) archive."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>"""

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", build_document_xml())
        zf.writestr("word/_rels/document.xml.rels", doc_rels)

    return buf.getvalue()


if __name__ == "__main__":
    output = Path(__file__).parent / "edge_content_controls.docx"
    output.write_bytes(build_docx())
    print(f"Created {output}")
