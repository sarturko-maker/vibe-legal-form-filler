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
        'write_answers(file_path="form.docx", answers=[{"pair_id": "T1-R2-C2", '
        '"answer_text": "Acme Corp"}])'
    ),
    "verify_output": (
        'verify_output(file_path="filled.docx", expected_answers=[{"pair_id": '
        '"q1", "expected_text": "Acme Corp"}])'
    ),
}


def _is_provided(value: str | None) -> bool:
    """Return True only if value is not None and has non-whitespace content.

    This is the single source of truth for "is this field provided?" across
    both answer_text and insertion_xml fields. Empty strings and
    whitespace-only strings are treated as not provided.
    """
    return value is not None and value.strip() != ""


def _validate_answer_text_xml_fields(answer_dicts: list[dict]) -> None:
    """Enforce exactly-one-of semantics for answer_text/insertion_xml.

    Iterates ALL answer dicts and collects errors (no short-circuiting).
    If any errors exist, raises ValueError with all of them listed.
    The 'value' key is also checked as an alias for insertion_xml
    (used by the relaxed Excel/PDF path).
    """
    errors: list[str] = []
    for i, a in enumerate(answer_dicts):
        pair_id = a.get("pair_id", "<missing>")
        has_answer_text = _is_provided(a.get("answer_text"))
        has_insertion_xml = (
            _is_provided(a.get("insertion_xml"))
            or _is_provided(a.get("value"))
        )
        if has_answer_text and has_insertion_xml:
            errors.append(
                f"Answer '{pair_id}' (index {i}): Both `answer_text` and "
                f"`insertion_xml` provided -- use one, not both. Use "
                f"`answer_text` for plain text, `insertion_xml` for "
                f"structured OOXML."
            )
        elif not has_answer_text and not has_insertion_xml:
            errors.append(
                f"Answer '{pair_id}' (index {i}): Neither `answer_text` "
                f"nor `insertion_xml` provided. Use `answer_text` for "
                f"plain text answers, `insertion_xml` for structured OOXML."
            )
    if errors:
        raise ValueError(
            f"write_answers validation failed "
            f"({len(errors)} invalid answer(s)):\n"
            + "\n".join(errors)
        )


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
        msg = str(exc)
        if tool_name == "write_answers" and "Neither was supplied" in msg:
            raise ValueError(
                "Missing file_path -- this is the path you passed "
                "to extract_structure_compact"
            ) from exc
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

_ALL_KNOWN_FIELDS = {"pair_id", "xpath", "mode", "confidence", "answer_text", "insertion_xml"}


def build_answer_payloads(
    answer_dicts: list[dict],
    ft: FileType,
    file_bytes: bytes | None = None,
) -> tuple[list[AnswerPayload], list[str]]:
    """Build AnswerPayload list with rich errors per dict on failure.

    Returns (payloads, warnings). Warnings are non-empty only when
    cross-check detects a mismatch between agent xpath and resolved xpath.
    """
    if ft == FileType.WORD:
        return _build_word_payloads(answer_dicts, file_bytes)
    return _build_relaxed_payloads(answer_dicts, file_bytes)


def _resolve_if_needed(
    answer_dicts: list[dict],
    ft: FileType,
    file_bytes: bytes | None,
) -> tuple[dict[str, str], list[str]]:
    """Delegate to pair_id_resolver.resolve_if_needed."""
    from src.pair_id_resolver import resolve_if_needed
    return resolve_if_needed(answer_dicts, ft, file_bytes, _is_provided)


def _build_word_payloads(
    answer_dicts: list[dict],
    file_bytes: bytes | None = None,
) -> tuple[list[AnswerPayload], list[str]]:
    """Word requires pair_id plus exactly one of answer_text/insertion_xml.

    When answer_text is provided, xpath and mode are optional (resolved
    from pair_id and defaulted to replace_content). When insertion_xml
    is provided, xpath and mode are still required.
    """
    # Per-answer required-field check (context-dependent)
    for i, a in enumerate(answer_dicts):
        received = sorted(a.keys())
        has_answer_text = _is_provided(a.get("answer_text"))
        has_insertion_xml = _is_provided(a.get("insertion_xml"))

        if "pair_id" not in a:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: ['pair_id']\n"
                f"  Example: {USAGE['write_answers']}"
            )

        # insertion_xml path requires explicit xpath and mode
        if has_insertion_xml and not has_answer_text:
            missing = [f for f in ("xpath", "mode") if f not in a]
            if missing:
                raise ValueError(
                    f"write_answers validation error in answers[{i}]:\n"
                    f"  Received keys: {received}\n"
                    f"  Missing required for insertion_xml path: {missing}\n"
                    f"  insertion_xml requires explicit xpath and mode.\n"
                    f"  Valid 'mode' values: {enum_values(InsertionMode)}\n"
                    f"  Example: {USAGE['write_answers']}"
                )

        unexpected = [k for k in a if k not in _ALL_KNOWN_FIELDS]
        if unexpected:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Unexpected fields: {unexpected}\n"
                f"  write_answers accepts: pair_id, xpath, "
                f"mode, plus answer_text or insertion_xml\n"
                f"  Optional: confidence\n"
                f"  Example: {USAGE['write_answers']}"
            )

    # Batch validation: exactly one of answer_text/insertion_xml per answer
    _validate_answer_text_xml_fields(answer_dicts)

    # Resolve pair_ids to xpaths when needed
    resolved, warnings = _resolve_if_needed(
        answer_dicts, FileType.WORD, file_bytes
    )

    results: list[AnswerPayload] = []
    for i, a in enumerate(answer_dicts):
        has_answer_text = _is_provided(a.get("answer_text"))
        pair_id = a["pair_id"]

        # Resolve xpath from pair_id when missing
        xpath = a.get("xpath")
        if not xpath and has_answer_text:
            xpath = resolved.get(pair_id)
            if not xpath:
                raise ValueError(
                    f"Answer '{pair_id}' (index {i}): No xpath provided "
                    f"and pair_id could not be resolved. Re-extract with "
                    f"extract_structure_compact to get current IDs."
                )
        elif xpath and pair_id in resolved:
            # Cross-check already handled; use resolved xpath
            if resolved[pair_id] != xpath:
                xpath = resolved[pair_id]

        # Default mode to replace_content for answer_text
        mode_raw = a.get("mode")
        if mode_raw is None and has_answer_text:
            mode = InsertionMode.REPLACE_CONTENT
        elif mode_raw is not None:
            try:
                mode = InsertionMode(mode_raw)
            except ValueError:
                raise ValueError(
                    f"write_answers validation error in answers[{i}]:\n"
                    f"  Invalid mode '{mode_raw}'.\n"
                    f"  Valid values: {enum_values(InsertionMode)}\n"
                    f"  Example: {USAGE['write_answers']}"
                )
        else:
            mode = InsertionMode.REPLACE_CONTENT

        try:
            results.append(AnswerPayload(
                pair_id=pair_id,
                xpath=xpath,
                insertion_xml=a.get("insertion_xml"),
                answer_text=a.get("answer_text"),
                mode=mode,
                **({"confidence": Confidence(a["confidence"])}
                   if "confidence" in a else {}),
            ))
        except ValueError as exc:
            received = sorted(a.keys())
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Error: {exc}\n"
                f"  Valid 'confidence' values: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['write_answers']}"
            ) from exc
    return results, warnings


def _build_relaxed_payloads(
    answer_dicts: list[dict],
    file_bytes: bytes | None = None,
) -> tuple[list[AnswerPayload], list[str]]:
    """Excel and PDF use relaxed field names (cell_id/field_id, value).

    answer_text is accepted as an alias for value/insertion_xml on the
    relaxed path, so Excel/PDF callers can use the same field name.
    When xpath/cell_id/field_id is missing, resolves from pair_id.
    """
    # Batch validation: exactly one of answer_text/insertion_xml/value per answer
    _validate_answer_text_xml_fields(answer_dicts)

    for i, a in enumerate(answer_dicts):
        received = sorted(a.keys())
        if "pair_id" not in a:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: ['pair_id']\n"
                f"  Required: pair_id (str), plus xpath/cell_id/field_id "
                f"(str), value/insertion_xml/answer_text (str)\n"
                f"  Example: {USAGE['write_answers']}"
            )

    # On the relaxed path (Excel/PDF), pair_id IS the element ID (S1-R2-C2 / F1)
    # so resolution means using pair_id directly -- no re-extraction needed.
    warnings: list[str] = []

    results: list[AnswerPayload] = []
    for i, a in enumerate(answer_dicts):
        pair_id = a["pair_id"]

        # Use provided xpath, or fall back to pair_id (which IS the element ID)
        xpath = a.get("xpath") or a.get("cell_id") or a.get("field_id", "")
        if not xpath:
            xpath = pair_id

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
            pair_id=pair_id,
            xpath=xpath,
            insertion_xml=(
                a.get("insertion_xml")
                or a.get("value")
                or a.get("answer_text", "")
            ),
            answer_text=a.get("answer_text"),
            mode=mode,
        ))
    return results, warnings


# ── ExpectedAnswer (verify_output) wrapper ───────────────────────────────────

_EXPECTED_REQUIRED = ("pair_id", "expected_text")


def validate_expected_answers(
    expected_answers: list[dict],
    ft: FileType | None = None,
    file_bytes: bytes | None = None,
) -> tuple[list[ExpectedAnswer], list[str], list[str | None]]:
    """Build ExpectedAnswer list with rich errors on validation failure.

    When ft and file_bytes are provided, resolves pair_ids to xpaths and
    cross-checks agent-provided xpaths against resolved xpaths. Returns
    (answers, warnings, resolved_from_list).

    When ft and file_bytes are both None (backward-compatible call), xpath
    is required, no resolution is performed, and resolved_from_list is
    all-None.
    """
    # Required-field check
    for i, a in enumerate(expected_answers):
        received = sorted(a.keys())
        missing = [f for f in _EXPECTED_REQUIRED if f not in a]
        if missing:
            raise ValueError(
                f"verify_output validation error in expected_answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Missing required: {missing}\n"
                f"  Required: pair_id (str), expected_text (str)\n"
                f"  Optional: xpath (str), confidence (str, default 'known') "
                f"— valid: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['verify_output']}"
            )

    # Backward-compatible: no resolution when ft/file_bytes not provided
    if ft is None or file_bytes is None:
        # xpath is required in backward-compatible mode
        for i, a in enumerate(expected_answers):
            if not a.get("xpath"):
                received = sorted(a.keys())
                raise ValueError(
                    f"verify_output validation error in expected_answers[{i}]:\n"
                    f"  Received keys: {received}\n"
                    f"  Missing required: ['xpath']\n"
                    f"  Required: pair_id (str), expected_text (str)\n"
                    f"  Optional: xpath (str), confidence (str, default 'known') "
                    f"— valid: {enum_values(Confidence)}\n"
                    f"  Example: {USAGE['verify_output']}"
                )
        results: list[ExpectedAnswer] = []
        for i, a in enumerate(expected_answers):
            try:
                results.append(ExpectedAnswer(**a))
            except Exception as exc:
                received = sorted(a.keys())
                raise ValueError(
                    f"verify_output validation error in expected_answers[{i}]:\n"
                    f"  Received keys: {received}\n"
                    f"  Error: {exc}\n"
                    f"  Required: pair_id (str), expected_text (str)\n"
                    f"  Optional: xpath (str), confidence (str, default 'known') "
                    f"— valid: {enum_values(Confidence)}\n"
                    f"  Example: {USAGE['verify_output']}"
                ) from exc
        return results, [], [None] * len(results)

    # Resolution path: resolve pair_ids and cross-check xpaths
    needs_resolution = any(not a.get("xpath") and a.get("pair_id") for a in expected_answers)
    needs_cross_check = any(a.get("xpath") and a.get("pair_id") for a in expected_answers)

    resolved: dict[str, str] = {}
    warnings: list[str] = []

    if needs_resolution or needs_cross_check:
        pair_ids = [a["pair_id"] for a in expected_answers if a.get("pair_id")]
        if ft in (FileType.EXCEL, FileType.PDF):
            # Relaxed path: pair_id IS the element ID (no re-extraction)
            resolved = {pid: pid for pid in pair_ids}
        else:
            # Word path: re-extract to resolve pair_ids to xpaths
            from src.pair_id_resolver import resolve_pair_ids, cross_check_xpaths
            resolved = resolve_pair_ids(file_bytes, ft, pair_ids)
            warnings = cross_check_xpaths(expected_answers, resolved)

    # Build ExpectedAnswer with resolved xpaths
    results = []
    resolved_from_list: list[str | None] = []
    for i, a in enumerate(expected_answers):
        pair_id = a.get("pair_id", "")
        xpath = a.get("xpath")

        if not xpath and pair_id:
            # Resolve from pair_id
            xpath = resolved.get(pair_id)
            if not xpath and ft in (FileType.EXCEL, FileType.PDF):
                # Identity fallback for Excel/PDF
                xpath = pair_id
            if not xpath:
                raise ValueError(
                    f"verify_output error: pair_id '{pair_id}' could not be "
                    f"resolved to an xpath. Re-extract with "
                    f"extract_structure_compact to get current IDs."
                )
            resolved_from_list.append("pair_id")
        elif (
            xpath
            and ft == FileType.WORD
            and pair_id in resolved
            and resolved[pair_id] != xpath
        ):
            # Cross-check mismatch (Word only): pair_id takes precedence
            xpath = resolved[pair_id]
            resolved_from_list.append("pair_id")
        elif xpath:
            resolved_from_list.append("xpath")
        else:
            resolved_from_list.append(None)

        # Build the answer with the resolved xpath
        answer_kwargs = dict(a)
        answer_kwargs["xpath"] = xpath
        try:
            results.append(ExpectedAnswer(**answer_kwargs))
        except Exception as exc:
            received = sorted(a.keys())
            raise ValueError(
                f"verify_output validation error in expected_answers[{i}]:\n"
                f"  Received keys: {received}\n"
                f"  Error: {exc}\n"
                f"  Required: pair_id (str), expected_text (str)\n"
                f"  Optional: xpath (str), confidence (str, default 'known') "
                f"— valid: {enum_values(Confidence)}\n"
                f"  Example: {USAGE['verify_output']}"
            ) from exc

    return results, warnings, resolved_from_list
