"""Word (.docx) handler — extract, validate, build XML, write.

This is the main entry point for all Word document operations. Extract and
validate logic lives here; write and field detection are in word_writer.py
and word_fields.py respectively.
"""

from __future__ import annotations

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
    LocationSnippet,
    LocationStatus,
    ValidatedLocation,
)
from src.xml_utils import (
    NAMESPACES,
    build_run_xml,
    extract_formatting,
    find_snippet_in_body,
    is_well_formed_ooxml,
)

from src.handlers.word_fields import (
    _get_context_text,
    list_form_fields as _list_form_fields_impl,
)
from src.handlers.word_writer import write_answers as _write_answers_impl

WORD_NAMESPACE_URI = NAMESPACES["w"]


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


def write_answers(file_bytes: bytes, answers: list[AnswerPayload]) -> bytes:
    """Insert answers at the specified XPaths and return the modified .docx bytes."""
    doc_xml = _read_document_xml(file_bytes)
    return _write_answers_impl(doc_xml, file_bytes, answers)


def list_form_fields(file_bytes: bytes) -> list[FormField]:
    """Detect empty table cells and placeholder text as fillable targets."""
    doc_xml = _read_document_xml(file_bytes)
    return _list_form_fields_impl(doc_xml)
