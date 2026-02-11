"""Word (.docx) handler — extract, validate, build XML, write."""

from __future__ import annotations

import re
import zipfile
from io import BytesIO

from lxml import etree

from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    BuildInsertionXmlResponse,
    ExtractStructureResponse,
    FormField,
    InsertionMode,
    LocationSnippet,
    LocationStatus,
    ValidatedLocation,
)
from src.xml_utils import (
    NAMESPACES,
    _parse_snippet,
    build_run_xml,
    extract_formatting,
    find_snippet_in_body,
    is_well_formed_ooxml,
)

W_NS = NAMESPACES["w"]


def _read_document_xml(file_bytes: bytes) -> bytes:
    """Extract word/document.xml from a .docx ZIP archive."""
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        return zf.read("word/document.xml")


def _get_body_xml(file_bytes: bytes) -> str:
    """Extract the <w:body> XML string from a .docx file."""
    doc_xml = _read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")
    return etree.tostring(body, encoding="unicode")


def extract_structure(file_bytes: bytes) -> ExtractStructureResponse:
    """Read a .docx and return the full <w:body> XML as a string."""
    body_xml = _get_body_xml(file_bytes)
    return ExtractStructureResponse(body_xml=body_xml)


def _get_context_text(element: etree._Element, max_chars: int = 100) -> str:
    """Get neighbouring text content for human review context."""
    texts: list[str] = []
    for t_elem in element.iter(f"{{{W_NS}}}t"):
        if t_elem.text:
            texts.append(t_elem.text)
    text = " ".join(texts)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def validate_locations(
    file_bytes: bytes, locations: list[LocationSnippet]
) -> list[ValidatedLocation]:
    """Match each OOXML snippet against the document body."""
    body_xml = _get_body_xml(file_bytes)
    body_root = etree.fromstring(body_xml.encode("utf-8"))

    results: list[ValidatedLocation] = []
    for loc in locations:
        xpaths = find_snippet_in_body(body_xml, loc.snippet)

        if len(xpaths) == 0:
            results.append(ValidatedLocation(
                pair_id=loc.pair_id,
                status=LocationStatus.NOT_FOUND,
            ))
        elif len(xpaths) == 1:
            # Get context text from the matched element
            matched = body_root.xpath(xpaths[0], namespaces=NAMESPACES)
            context = ""
            if matched:
                context = _get_context_text(matched[0])
            results.append(ValidatedLocation(
                pair_id=loc.pair_id,
                status=LocationStatus.MATCHED,
                xpath=xpaths[0],
                context=context,
            ))
        else:
            results.append(ValidatedLocation(
                pair_id=loc.pair_id,
                status=LocationStatus.AMBIGUOUS,
                context=f"Snippet matched {len(xpaths)} locations",
            ))

    return results


def build_insertion_xml(request: BuildInsertionXmlRequest) -> BuildInsertionXmlResponse:
    """Build a <w:r> element inheriting formatting from the target location.

    For plain_text: extract formatting from target_context_xml and wrap
    answer_text in a <w:r> with that formatting.

    For structured: validate the AI-provided OOXML.
    """
    if request.answer_type == AnswerType.PLAIN_TEXT:
        formatting = extract_formatting(request.target_context_xml)
        run_xml = build_run_xml(request.answer_text, formatting)
        return BuildInsertionXmlResponse(insertion_xml=run_xml, valid=True)

    elif request.answer_type == AnswerType.STRUCTURED:
        valid, error = is_well_formed_ooxml(request.answer_text)
        if valid:
            return BuildInsertionXmlResponse(
                insertion_xml=request.answer_text, valid=True
            )
        else:
            return BuildInsertionXmlResponse(
                insertion_xml="", valid=False, error=error
            )

    return BuildInsertionXmlResponse(
        insertion_xml="", valid=False,
        error=f"Unknown answer_type: {request.answer_type}",
    )


def _replace_content(target: etree._Element, insertion_xml: str) -> None:
    """Clear existing content in target and insert new XML."""
    # Remove all child elements except pPr (paragraph properties)
    for child in list(target):
        if child.tag != f"{{{W_NS}}}pPr":
            target.remove(child)
    # Clear any direct text
    target.text = None

    # Parse and insert the new content
    new_elem = _parse_snippet(insertion_xml)
    if new_elem is not None:
        target.append(new_elem)


def _append_content(target: etree._Element, insertion_xml: str) -> None:
    """Append new content after existing content in target."""
    new_elem = _parse_snippet(insertion_xml)
    if new_elem is not None:
        target.append(new_elem)


def _replace_placeholder(
    target: etree._Element, insertion_xml: str, placeholder: str | None = None
) -> None:
    """Find placeholder text within the target and replace it.

    If no specific placeholder is given, looks for common patterns:
    [Enter here], [Enter ...], ___ (3+ underscores).
    """
    placeholder_patterns = [
        re.compile(r"\[Enter[^\]]*\]"),
        re.compile(r"_{3,}"),
    ]

    new_elem = _parse_snippet(insertion_xml)
    if new_elem is None:
        return

    # Get the text from the new element
    new_text_elem = new_elem.find(f".//{{{W_NS}}}t")
    new_text = new_text_elem.text if new_text_elem is not None else ""

    # Search through all <w:t> elements in the target
    for t_elem in target.iter(f"{{{W_NS}}}t"):
        if t_elem.text is None:
            continue

        if placeholder:
            if placeholder in t_elem.text:
                t_elem.text = t_elem.text.replace(placeholder, new_text)
                return
        else:
            for pattern in placeholder_patterns:
                match = pattern.search(t_elem.text)
                if match:
                    t_elem.text = pattern.sub(new_text, t_elem.text)
                    return


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Insert answers at the specified XPaths and return the modified .docx bytes."""
    # Read the document XML
    doc_xml = _read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")

    for answer in answers:
        # Find the target element by XPath
        # The XPath from find_snippet_in_body is relative to body,
        # starting with / — we need to search from body
        matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
        if not matched:
            raise ValueError(
                f"XPath '{answer.xpath}' for pair_id '{answer.pair_id}' "
                f"did not match any element in the document"
            )
        target = matched[0]

        if answer.mode == InsertionMode.REPLACE_CONTENT:
            _replace_content(target, answer.insertion_xml)
        elif answer.mode == InsertionMode.APPEND:
            _append_content(target, answer.insertion_xml)
        elif answer.mode == InsertionMode.REPLACE_PLACEHOLDER:
            _replace_placeholder(target, answer.insertion_xml)

    # Serialise the modified XML back
    modified_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                  standalone=True)

    # Rewrite the .docx with the modified document.xml
    output = BytesIO()
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf_in:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                if item.filename == "word/document.xml":
                    zf_out.writestr(item, modified_xml)
                else:
                    zf_out.writestr(item, zf_in.read(item.filename))

    return output.getvalue()


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Detect empty table cells and placeholder text as fillable targets.

    Heuristics:
    1. Empty table cells following a cell with text (question → answer pattern)
    2. Paragraphs containing common placeholder patterns ([Enter here], ___)
    """
    doc_xml = _read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        return []

    fields: list[FormField] = []
    field_counter = 0

    # 1. Table-based: empty cells following cells with text
    for tbl in body.iter(f"{{{W_NS}}}tbl"):
        for tr in tbl.iter(f"{{{W_NS}}}tr"):
            cells = list(tr.iter(f"{{{W_NS}}}tc"))
            for i in range(len(cells) - 1):
                q_cell = cells[i]
                a_cell = cells[i + 1]
                q_text = _get_context_text(q_cell).strip()
                a_text = _get_context_text(a_cell).strip()
                if q_text and not a_text:
                    field_counter += 1
                    fields.append(FormField(
                        field_id=f"field_{field_counter}",
                        label=q_text,
                        field_type="table_cell",
                    ))

    # 2. Paragraph-based: placeholder patterns
    placeholder_patterns = [
        re.compile(r"\[Enter[^\]]*\]"),
        re.compile(r"_{3,}"),
    ]
    for p_elem in body.iter(f"{{{W_NS}}}p"):
        p_text = _get_context_text(p_elem)
        for pattern in placeholder_patterns:
            match = pattern.search(p_text)
            if match:
                field_counter += 1
                fields.append(FormField(
                    field_id=f"field_{field_counter}",
                    label=p_text.strip(),
                    field_type="placeholder",
                    current_value=match.group(),
                ))
                break  # One field per paragraph

    return fields
