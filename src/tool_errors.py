"""Validation wrappers that produce rich, agent-friendly error messages.

Each wrapper replaces inline model construction in tools_extract.py and
tools_write.py. When an agent passes bad inputs, the error names the exact
problem, shows received vs expected, lists enum values, and includes a
mini usage example — so any agent can self-correct in one retry.
"""

from __future__ import annotations

from enum import Enum

from src.models import (
    AnswerPayload,
    AnswerType,
    Confidence,
    ExpectedAnswer,
    FileType,
    InsertionMode,
    LocationSnippet,
)
from src.validators import resolve_file_input


# ── Usage examples per tool ──────────────────────────────────────────────────

USAGE: dict[str, str] = {
    "extract_structure_compact": (
        'extract_structure_compact(file_path="form.docx")'
    ),
    "extract_structure": (
        'extract_structure(file_path="form.docx")'
    ),
    "validate_locations": (
        'validate_locations(file_path="form.docx", '
        'locations=[{"pair_id": "q1", "snippet": "<w:t>Company</w:t>"}])'
    ),
    "build_insertion_xml": (
        'build_insertion_xml(answer_text="Acme Corp", '
        'target_context_xml="<w:r>...</w:r>", answer_type="plain_text")'
    ),
    "list_form_fields": (
        'list_form_fields(file_path="form.docx")'
    ),
    "write_answers": (
        'write_answers(file_path="form.docx", answers=[{"pair_id": "q1", '
        '"xpath": "/w:body/...", "insertion_xml": "<w:r>...</w:r>", '
        '"mode": "replace_content"}])'
    ),
    "verify_output": (
        'verify_output(file_path="filled.docx", expected_answers=[{"pair_id": '
        '"q1", "xpath": "/w:body/...", "expected_text": "Acme Corp"}])'
    ),
}


def enum_values(enum_cls: type[Enum]) -> str:
    """Return a formatted string of all enum member values."""
    return ", ".join(f"'{m.value}'" for m in enum_cls)


# ── File input wrapper ───────────────────────────────────────────────────────

def resolve_file_for_tool(
    tool_name: str,
    file_bytes_b64: str | None,
    file_type: str | None,
    file_path: str | None,
) -> tuple[bytes, FileType]:
    """Wrap resolve_file_input with tool-specific context on failure."""
    try:
        return resolve_file_input(file_bytes_b64, file_type, file_path)
    except ValueError as exc:
        example = USAGE.get(tool_name, tool_name)
        raise ValueError(
            f"{tool_name} error: {exc}\n"
            f"  Example: {example}"
        ) from exc


# ── LocationSnippet wrapper ──────────────────────────────────────────────────

_LOCATION_REQUIRED = ("pair_id", "snippet")


def validate_location_snippets(
    locations: list[dict],
) -> list[LocationSnippet]:
    """Build LocationSnippet list with rich errors on validation failure."""
    results: list[LocationSnippet] = []
    for i, loc in enumerate(locations):
        received = sorted(loc.keys())
        missing = [f for f in _LOCATION_REQUIRED if f not in loc]
        if missing:
            raise ValueError(
                f"validate_locations validation error in locations[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: {missing}\n"
                f"  Required: pair_id (str), snippet (str)\n"
                f"  Example: {USAGE['validate_locations']}"
            )
        try:
            results.append(LocationSnippet(**loc))
        except Exception as exc:
            raise ValueError(
                f"validate_locations validation error in locations[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Error: {exc}\n"
                f"  Required: pair_id (str), snippet (str)\n"
                f"  Example: {USAGE['validate_locations']}"
            ) from exc
    return results


# ── AnswerType wrapper ───────────────────────────────────────────────────────

def validate_answer_type(answer_type: str) -> AnswerType:
    """Parse AnswerType with a rich error listing valid values."""
    try:
        return AnswerType(answer_type)
    except ValueError:
        raise ValueError(
            f"build_insertion_xml error: invalid answer_type '{answer_type}'.\n"
            f"  Valid values: {enum_values(AnswerType)}\n"
            f"  Example: {USAGE['build_insertion_xml']}"
        )


# ── AnswerPayload (write_answers) wrapper ────────────────────────────────────

_WORD_REQUIRED = ("pair_id", "xpath", "insertion_xml", "mode")
_WORD_OPTIONAL = ("confidence",)
_ALL_KNOWN_FIELDS = {*_WORD_REQUIRED, *_WORD_OPTIONAL}


def build_answer_payloads(
    answer_dicts: list[dict], ft: FileType
) -> list[AnswerPayload]:
    """Build AnswerPayload list with rich errors per dict on failure."""
    if ft == FileType.WORD:
        return _build_word_payloads(answer_dicts)
    return _build_relaxed_payloads(answer_dicts)


def _build_word_payloads(answer_dicts: list[dict]) -> list[AnswerPayload]:
    """Word requires all four fields explicitly."""
    results: list[AnswerPayload] = []
    for i, a in enumerate(answer_dicts):
        received = sorted(a.keys())
        missing = [f for f in _WORD_REQUIRED if f not in a]
        if missing:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: {missing}\n"
                f"  Valid 'mode' values: {enum_values(InsertionMode)}\n"
                f"  Required: pair_id (str), xpath (str), "
                f"insertion_xml (str), mode (str)\n"
                f"  Optional: confidence (str, default 'known') "
                f"— valid: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['write_answers']}"
            )

        unexpected = [k for k in a if k not in _ALL_KNOWN_FIELDS]
        if unexpected:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Unexpected fields: {unexpected}\n"
                f"  write_answers requires: pair_id, xpath, "
                f"insertion_xml, mode\n"
                f"  Optional: confidence\n"
                f"  Example: {USAGE['write_answers']}"
            )

        try:
            mode = InsertionMode(a["mode"])
        except ValueError:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Invalid mode '{a['mode']}'.\n"
                f"  Valid values: {enum_values(InsertionMode)}\n"
                f"  Example: {USAGE['write_answers']}"
            )

        try:
            results.append(AnswerPayload(
                pair_id=a["pair_id"],
                xpath=a["xpath"],
                insertion_xml=a["insertion_xml"],
                mode=mode,
                **({"confidence": Confidence(a["confidence"])}
                   if "confidence" in a else {}),
            ))
        except ValueError as exc:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Error: {exc}\n"
                f"  Valid 'confidence' values: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['write_answers']}"
            ) from exc
    return results


def _build_relaxed_payloads(answer_dicts: list[dict]) -> list[AnswerPayload]:
    """Excel and PDF use relaxed field names (cell_id/field_id, value)."""
    results: list[AnswerPayload] = []
    for i, a in enumerate(answer_dicts):
        received = sorted(a.keys())
        if "pair_id" not in a:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: ['pair_id']\n"
                f"  Required: pair_id (str), plus xpath/cell_id/field_id "
                f"(str), value/insertion_xml (str)\n"
                f"  Example: {USAGE['write_answers']}"
            )

        mode_raw = a.get("mode", InsertionMode.REPLACE_CONTENT.value)
        try:
            mode = InsertionMode(mode_raw)
        except ValueError:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Invalid mode '{mode_raw}'.\n"
                f"  Valid values: {enum_values(InsertionMode)}\n"
                f"  Example: {USAGE['write_answers']}"
            )

        results.append(AnswerPayload(
            pair_id=a["pair_id"],
            xpath=a.get("xpath") or a.get("cell_id") or a.get("field_id", ""),
            insertion_xml=(
                a.get("insertion_xml") or a.get("value", "")
            ),
            mode=mode,
        ))
    return results


# ── ExpectedAnswer (verify_output) wrapper ───────────────────────────────────

_EXPECTED_REQUIRED = ("pair_id", "xpath", "expected_text")


def validate_expected_answers(
    expected_answers: list[dict],
) -> list[ExpectedAnswer]:
    """Build ExpectedAnswer list with rich errors on validation failure."""
    results: list[ExpectedAnswer] = []
    for i, a in enumerate(expected_answers):
        received = sorted(a.keys())
        missing = [f for f in _EXPECTED_REQUIRED if f not in a]
        if missing:
            raise ValueError(
                f"verify_output validation error in expected_answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: {missing}\n"
                f"  Required: pair_id (str), xpath (str), "
                f"expected_text (str)\n"
                f"  Optional: confidence (str, default 'known') "
                f"— valid: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['verify_output']}"
            )
        try:
            results.append(ExpectedAnswer(**a))
        except Exception as exc:
            raise ValueError(
                f"verify_output validation error in expected_answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Error: {exc}\n"
                f"  Required: pair_id (str), xpath (str), "
                f"expected_text (str)\n"
                f"  Optional: confidence (str, default 'known') "
                f"— valid: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['verify_output']}"
            ) from exc
    return results
