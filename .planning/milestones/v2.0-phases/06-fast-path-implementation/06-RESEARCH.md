# Phase 6: Fast Path Implementation - Research

**Researched:** 2026-02-17
**Domain:** OOXML write path routing, formatting extraction from parsed elements, insertion mode adaptation
**Confidence:** HIGH

## Summary

Phase 6 implements the core fast path: when an agent provides `answer_text` (no `insertion_xml`) in a `write_answers` call, the server builds the insertion OOXML internally using the same formatting extraction and run-building logic that `build_insertion_xml` uses today. This eliminates the per-answer MCP round-trip that currently dominates form-filling time.

The codebase is well-prepared for this. Phase 5 delivered all foundation pieces: `answer_text` field on `AnswerPayload` (optional, defaults to `None`), `extract_formatting_from_element()` as a public function in `xml_formatting.py`, and batch validation enforcing exactly-one-of semantics. The remaining work is routing logic in `word_writer.py`'s `_apply_answer` function: detect when `answer_text` is provided, resolve the XPath target element, extract formatting from that element, build a `<w:r>` with `build_run_xml()`, and pass the resulting XML to the existing insertion mode functions (`_replace_content`, `_append_content`, `_replace_placeholder`).

The change is localized to two files: `word_writer.py` (routing logic and formatting extraction) and `word.py` (pass-through, already handles the delegation). No changes needed to `tools_write.py`, `tool_errors.py`, `models.py`, or `xml_formatting.py` -- Phase 5 already set those up.

**Primary recommendation:** Add a `_build_insertion_xml_from_answer_text()` helper in `word_writer.py` that takes the resolved target element and the `answer_text`, calls `extract_formatting_from_element()` + `build_run_xml()`, and returns the insertion XML string. Then update `_apply_answer()` to call this helper when `answer_text` is provided and `insertion_xml` is not.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FAST-01 | Server builds insertion OOXML from plain text internally when `answer_text` is provided in write_answers | Routing logic in `_apply_answer()` detects `answer_text`, calls `extract_formatting_from_element()` on the resolved target element, then `build_run_xml()` to produce the OOXML. Same two functions that `build_insertion_xml` MCP tool uses, just without the MCP round-trip. |
| FAST-02 | Fast path inherits formatting (font, size, bold, italic, color) from the target element identically to build_insertion_xml | Both paths use the same `extract_formatting_from_element()` -> `build_run_xml()` chain. The element-based function was specifically designed in Phase 5 for this purpose. `extract_formatting()` (string-based) delegates to `extract_formatting_from_element()` internally, so they share identical logic. |
| FAST-03 | All three insertion modes (replace_content, append, replace_placeholder) work with answer_text | The fast path builds the insertion XML string first, then passes it to the same mode functions (`_replace_content`, `_append_content`, `_replace_placeholder`). No mode-specific changes needed -- the modes already accept any well-formed OOXML string. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| lxml | 6.0.2 | XPath resolution, element inspection, formatting extraction | Already in use; `body.xpath()` resolves target elements, `extract_formatting_from_element()` reads their properties |
| pydantic | 2.12.5 | AnswerPayload model with `answer_text` field | Already in use; Phase 5 added the field, Phase 6 just reads it |
| pytest | 9.0.2 | Test framework | Already in use; 250 existing tests |

### Supporting
No new libraries needed. All changes use existing dependencies at their current versions.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Building XML in `_apply_answer()` | Building XML in `word.write_answers()` before calling `_write_answers_impl()` | `_apply_answer()` already has the resolved target element; building at the word.py level would require a second XPath resolution or passing the body down. **Recommendation: build in `_apply_answer()`** |
| Using `build_run_xml()` (string output) | Using lxml element construction directly | `build_run_xml()` returns a string that gets re-parsed by `parse_snippet()` in the mode functions. Could avoid the string round-trip by constructing elements directly, but that duplicates logic and the perf cost of one parse is negligible (~0.1ms). **Recommendation: use `build_run_xml()` for simplicity and single code path** |

## Architecture Patterns

### Recommended Approach

Changes touch 1 source file (plus tests):

```
src/
└── handlers/
    └── word_writer.py     # Add _build_insertion_xml_for_answer_text() helper,
                            # update _apply_answer() routing logic
```

No changes needed to:
- `src/models.py` -- already has `answer_text: str | None = None`
- `src/xml_formatting.py` -- already has `extract_formatting_from_element()`
- `src/tool_errors.py` -- already validates exactly-one-of
- `src/tools_write.py` -- already passes AnswerPayload through
- `src/handlers/word.py` -- already delegates to `_write_answers_impl()`

### Pattern 1: Fast Path Routing in `_apply_answer()`

**What:** Detect `answer_text` at the point where the target element is already resolved, build insertion XML from it, then pass to existing mode functions.

**When to use:** When the AnswerPayload has `answer_text` set and `insertion_xml` is None/empty.

**Example:**
```python
# In word_writer.py

from src.xml_formatting import extract_formatting_from_element, build_run_xml
from src.tool_errors import _is_provided


def _build_insertion_xml_for_answer_text(
    target: etree._Element, answer_text: str
) -> str:
    """Build insertion OOXML from plain text, inheriting formatting from target.

    This is the fast path: the server builds the same XML that
    build_insertion_xml would produce, without an MCP round-trip.
    Uses extract_formatting_from_element() on the resolved target
    element, then build_run_xml() to wrap the text.
    """
    formatting = extract_formatting_from_element(target)
    return build_run_xml(answer_text, formatting)


def _apply_answer(body: etree._Element, answer: AnswerPayload) -> None:
    """Locate a single answer's target by XPath and insert its content."""
    _validate_xpath(answer.xpath)
    matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
    if not matched:
        raise ValueError(
            f"XPath '{answer.xpath}' for pair_id '{answer.pair_id}' "
            f"did not match any element in the document"
        )
    target = matched[0]

    # Fast path: build insertion XML from answer_text
    if _is_provided(answer.answer_text):
        insertion_xml = _build_insertion_xml_for_answer_text(
            target, answer.answer_text
        )
    else:
        insertion_xml = answer.insertion_xml

    if answer.mode == InsertionMode.REPLACE_CONTENT:
        _replace_content(target, insertion_xml)
    elif answer.mode == InsertionMode.APPEND:
        _append_content(target, insertion_xml)
    elif answer.mode == InsertionMode.REPLACE_PLACEHOLDER:
        _replace_placeholder(target, insertion_xml)
```

**Critical detail:** The routing check uses `_is_provided(answer.answer_text)` -- the same helper that `_validate_answer_text_xml_fields` in tool_errors.py uses. This ensures consistent "is it provided?" semantics. Since the batch validation in tool_errors.py already guarantees exactly one of `answer_text`/`insertion_xml` is provided, the routing is deterministic and complete.

### Pattern 2: Formatting Extraction from Resolved Target

**What:** Extract formatting properties directly from the XPath-resolved element, instead of re-parsing a serialized XML string like `build_insertion_xml` does.

**Why this is correct:** `extract_formatting_from_element()` is the primary extraction path. `extract_formatting()` (string-based) delegates to it. So using the element-based version produces identical results while avoiding a serialize-then-reparse cycle.

**Formatting properties extracted:**
- `font_ascii`, `font_hAnsi`, `font_cs`, `font_eastAsia` (from `<w:rFonts>`)
- `sz`, `szCs` (from `<w:sz>`, `<w:szCs>`)
- `color` (from `<w:color>`)
- `bold`, `italic` (from `<w:b>`, `<w:i>`)
- `underline` (from `<w:u>`)

**Search order for `<w:rPr>`** (implemented in `_find_run_properties`):
1. Direct child `<w:rPr>` (element is a `<w:r>`)
2. First run's `<w:rPr>` (element is a `<w:p>` containing runs)
3. Paragraph-level `<w:rPr>` inside `<w:pPr>` (inherited default run formatting)

This is exactly the same search order used by the old `build_insertion_xml` → `extract_formatting()` path. No behavioral difference.

### Pattern 3: Reusing Existing Mode Functions Unchanged

**What:** The fast path builds an insertion XML string and passes it to the same `_replace_content()`, `_append_content()`, `_replace_placeholder()` functions. No mode-specific logic changes.

**Why this works:** These functions accept any well-formed OOXML string. The `build_run_xml()` output is a well-formed `<w:r>` element with namespace declarations -- exactly what the mode functions expect. The string goes through `parse_snippet()` inside each mode function, which handles namespace wrapping.

### Anti-Patterns to Avoid

- **Duplicating formatting extraction logic:** Do NOT copy the extraction code into word_writer.py. Import and call `extract_formatting_from_element()` from xml_formatting.py. Single source of truth.
- **Bypassing the existing mode functions:** Do NOT write separate insertion logic for the fast path. Build the XML string and pass it to the same `_replace_content` / `_append_content` / `_replace_placeholder`. The mode functions handle edge cases (wrapping `<w:r>` in `<w:p>` for table cells, preserving `tcPr`/`pPr`, placeholder regex matching).
- **Importing `_is_provided` from tool_errors for routing:** This is a private function (underscore prefix). While it works, a cleaner approach is to check `answer.answer_text is not None and answer.answer_text.strip()` directly, or to add a simple inline check. However, since `_is_provided` encapsulates the exact semantics (None/empty/whitespace = not provided) and is already the single source of truth, importing it is justified. The alternative of duplicating the check risks drift. **Recommendation: import `_is_provided` from tool_errors.py despite the underscore prefix, or add a `has_answer_text` property to AnswerPayload.**
- **Changing the mode function signatures:** Do NOT add an `answer_text` parameter to the mode functions. They operate on insertion XML strings. The fast path's job is to convert `answer_text` to an insertion XML string before reaching the mode functions.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Formatting extraction from lxml element | Custom rPr-walking code in word_writer.py | `extract_formatting_from_element()` from xml_formatting.py | Already handles all property types, all search paths, tested with parity tests |
| Run XML building with formatting | Manual `<w:r>` string concatenation | `build_run_xml()` from xml_formatting.py | Handles `xml:space="preserve"` for leading/trailing whitespace, namespace declarations, all formatting properties |
| "Is field provided?" check | Inline `if answer.answer_text and answer.answer_text.strip()` | `_is_provided()` from tool_errors.py | Centralizes the None/empty/whitespace semantics that Phase 5 established |

**Key insight:** The fast path is not new logic -- it is moving existing logic to a different execution point. `build_insertion_xml` already does `extract_formatting() + build_run_xml()`. The fast path does `extract_formatting_from_element() + build_run_xml()` at the point where the target element is already resolved. Same logic, fewer steps, no round-trip.

## Common Pitfalls

### Pitfall 1: Extracting Formatting from the Wrong Element Level
**What goes wrong:** The XPath might point to a `<w:tc>` (table cell), `<w:p>` (paragraph), or `<w:r>` (run). If extraction is done on a `<w:tc>`, `_find_run_properties()` must search deeper for the first run's rPr. If the cell is empty (no runs), formatting extraction returns `{}` and the answer gets no formatting.
**Why it happens:** The existing `build_insertion_xml` path receives `target_context_xml` which is typically a paragraph or run. The fast path receives whatever the XPath resolves to, which may be a cell.
**How to avoid:** This is already handled by `_find_run_properties()` which searches: direct child rPr, first run's rPr, pPr/rPr. For an empty cell (no runs, no pPr/rPr), returning `{}` is correct -- the answer gets default formatting, same as `build_insertion_xml` would produce with an empty `target_context_xml`.
**Warning signs:** Test with an empty table cell as target. If `build_run_xml("text", {})` produces a bare `<w:r><w:t>text</w:t></w:r>` with no rPr, that is correct.

### Pitfall 2: `insertion_xml` Being None Instead of a String
**What goes wrong:** The mode functions (`_replace_content`, `_append_content`, `_replace_placeholder`) currently receive `answer.insertion_xml` which is a string. With the fast path, if `answer_text` is provided, `insertion_xml` is `None`. If the routing check fails or is bypassed, `None` is passed to `parse_snippet()` which calls `.encode("utf-8")` and crashes with `AttributeError: 'NoneType' object has no attribute 'encode'`.
**Why it happens:** The mode functions were written when `insertion_xml` was a required string field (never None).
**How to avoid:** The routing in `_apply_answer()` must guarantee that one of `answer_text` or `insertion_xml` is provided (already enforced by batch validation in tool_errors.py). The fast path builds the `insertion_xml` string from `answer_text`, so by the time the mode function runs, it always receives a string. Assign the built XML to a local `insertion_xml` variable and pass that.
**Warning signs:** `AttributeError` or `TypeError` when processing an answer with `answer_text` but no `insertion_xml`.

### Pitfall 3: File Size Limit on word_writer.py
**What goes wrong:** word_writer.py is currently 182 lines. Adding the new helper function and updating `_apply_answer()` could push it over the 200-line limit established in CLAUDE.md.
**Why it happens:** The helper function (`_build_insertion_xml_for_answer_text`) adds ~10 lines, and the routing change in `_apply_answer()` adds ~5 lines, totaling ~195 lines.
**How to avoid:** The 200-line limit should accommodate this change. If it gets tight, the `_XPATH_SAFE_RE` regex and `_validate_xpath()` function (12 lines) could be moved to a shared module, but this is unlikely to be necessary.
**Warning signs:** Line count approaching 200 after implementation.

### Pitfall 4: Import Cycle Risk
**What goes wrong:** `word_writer.py` needs to import `extract_formatting_from_element` and `build_run_xml` from `xml_formatting.py`. It currently imports from `xml_utils.py` (the barrel). Adding a new import from `tool_errors.py` for `_is_provided` could create unexpected coupling.
**Why it happens:** `word_writer.py` currently imports only from `src.models`, `src.xml_utils`. Adding `src.tool_errors` or `src.xml_formatting` is new.
**How to avoid:** Import from `src.xml_utils` (which re-exports `extract_formatting_from_element` and `build_run_xml`) to keep imports consistent with the existing pattern. For `_is_provided`, either inline the check or use a simple `answer.answer_text is not None` check (Phase 5 validation already guarantees non-empty when present).
**Warning signs:** `ImportError` at module load time.

### Pitfall 5: Forgetting to Test All Three Modes with answer_text
**What goes wrong:** Implementing replace_content and forgetting that append and replace_placeholder also need to work.
**Why it happens:** replace_content is the most common mode; the other two are easy to forget.
**How to avoid:** The routing logic is mode-agnostic -- it builds the insertion XML string before the mode switch. But tests must explicitly verify all three modes with `answer_text` input.
**Warning signs:** Tests only cover `replace_content` mode.

## Code Examples

Verified patterns from the actual codebase:

### Current `_apply_answer()` (will change)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/handlers/word_writer.py, line 143
def _apply_answer(body: etree._Element, answer: AnswerPayload) -> None:
    """Locate a single answer's target by XPath and insert its content."""
    _validate_xpath(answer.xpath)
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
```

### Existing `build_insertion_xml` in word.py (what we replicate)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/handlers/word.py, line 60
def build_insertion_xml(request: BuildInsertionXmlRequest) -> BuildInsertionXmlResponse:
    if request.answer_type == AnswerType.PLAIN_TEXT:
        formatting = extract_formatting(request.target_context_xml)
        run_xml = build_run_xml(request.answer_text, formatting)
        return BuildInsertionXmlResponse(insertion_xml=run_xml, valid=True)
```

### Existing `extract_formatting_from_element()` (already available from Phase 5)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/xml_formatting.py, line 124
def extract_formatting_from_element(elem: etree._Element) -> dict:
    rpr = _find_run_properties(elem)
    if rpr is None:
        return {}
    formatting: dict = {}
    formatting.update(_extract_font_properties(rpr))
    formatting.update(_extract_size_and_color(rpr))
    formatting.update(_extract_style_properties(rpr))
    return formatting
```

### Existing `build_run_xml()` (already available)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/xml_formatting.py, line 193
def build_run_xml(text: str, formatting: dict) -> str:
    w = NAMESPACES["w"]
    r_elem = etree.Element(f"{{{w}}}r")
    if formatting:
        rpr = etree.SubElement(r_elem, f"{{{w}}}rPr")
        _apply_font_properties(rpr, formatting)
        _apply_style_properties(rpr, formatting)
        _apply_size_and_color(rpr, formatting)
    t_elem = etree.SubElement(r_elem, f"{{{w}}}t")
    t_elem.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return etree.tostring(r_elem, encoding="unicode")
```

### How mode functions consume insertion_xml (unchanged)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/handlers/word_writer.py
# _replace_content (line 43): parse_snippet(insertion_xml) -> appends element
# _append_content (line 74): parse_snippet(insertion_xml) -> appends element
# _replace_placeholder (line 81): parse_snippet(insertion_xml) -> extracts text
```

### New helper function (to add in word_writer.py)
```python
def _build_insertion_xml_for_answer_text(
    target: etree._Element, answer_text: str
) -> str:
    """Build insertion OOXML from plain text, inheriting formatting from target.

    This is the fast path: the server builds the same XML that the
    build_insertion_xml MCP tool would produce, without an extra round-trip.
    """
    formatting = extract_formatting_from_element(target)
    return build_run_xml(answer_text, formatting)
```

### Updated `_apply_answer()` (target implementation)
```python
def _apply_answer(body: etree._Element, answer: AnswerPayload) -> None:
    """Locate a single answer's target by XPath and insert its content."""
    _validate_xpath(answer.xpath)
    matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
    if not matched:
        raise ValueError(
            f"XPath '{answer.xpath}' for pair_id '{answer.pair_id}' "
            f"did not match any element in the document"
        )
    target = matched[0]

    # Fast path: build insertion XML from answer_text when present
    if answer.answer_text is not None and answer.answer_text.strip():
        insertion_xml = _build_insertion_xml_for_answer_text(
            target, answer.answer_text
        )
    else:
        insertion_xml = answer.insertion_xml

    if answer.mode == InsertionMode.REPLACE_CONTENT:
        _replace_content(target, insertion_xml)
    elif answer.mode == InsertionMode.APPEND:
        _append_content(target, insertion_xml)
    elif answer.mode == InsertionMode.REPLACE_PLACEHOLDER:
        _replace_placeholder(target, insertion_xml)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Agent calls `build_insertion_xml` per answer (N round-trips) | Agent provides `answer_text` in `write_answers` (0 extra round-trips) | Phase 6 | For 30 answers: eliminates 30 MCP round-trips. Agent context window freed from managing 30 XML strings. |
| `insertion_xml` required on every AnswerPayload | `answer_text` OR `insertion_xml` required (exactly one) | Phase 5 | Backward-compatible: existing callers still work. New callers use simpler API. |
| Formatting extracted from XML string | Formatting extracted from pre-parsed lxml element | Phase 5 | Avoids serialize-then-reparse when element is already available from XPath resolution |

## Open Questions

1. **Should `_is_provided` be imported from tool_errors or should the check be inlined?**
   - What we know: `_is_provided` is a private function (underscore prefix) in tool_errors.py. Importing it from word_writer.py crosses module boundaries and relies on an implementation detail.
   - What's unclear: Whether the import coupling is worse than duplicating the logic.
   - Recommendation: **Inline the check** as `answer.answer_text is not None and answer.answer_text.strip()`. The batch validation in tool_errors.py already guarantees that if `answer_text` is provided, it is non-None and non-empty after stripping. So in practice, `answer.answer_text is not None` is sufficient. But including the `.strip()` check makes the code self-documenting and safe against future validation changes.

2. **Should the fast path be tested against `build_insertion_xml` for parity?**
   - What we know: Both paths use the same underlying functions (`extract_formatting_from_element` and `build_run_xml`). If the functions produce identical results, the paths produce identical results.
   - What's unclear: Whether edge cases in element resolution (XPath pointing to different element types) could cause differences.
   - Recommendation: **Yes, add a parity test in Phase 7 (QA-01).** Phase 6 tests should verify the fast path works correctly. Phase 7 adds the explicit parity comparison. For Phase 6, test that the answer appears with correct formatting for each mode.

3. **What happens if answer_text contains XML special characters?**
   - What we know: `build_run_xml()` sets `t_elem.text = text` which lxml auto-escapes (`&` -> `&amp;`, `<` -> `&lt;`, etc.). This is correct behavior -- the text is literal, not XML.
   - What's unclear: Nothing -- this is well-defined.
   - Recommendation: **No special handling needed.** lxml handles escaping. Add an edge-case test with `&`, `<`, `>`, `"`, `'` in answer_text to confirm (in Phase 7 per QA-02, or as a bonus in Phase 6).

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/handlers/word_writer.py` (line 143: `_apply_answer`, lines 43-115: mode functions)
- Codebase inspection: `src/handlers/word.py` (line 60: `build_insertion_xml` -- the function we replicate)
- Codebase inspection: `src/xml_formatting.py` (line 124: `extract_formatting_from_element`, line 193: `build_run_xml`)
- Codebase inspection: `src/models.py` (line 126: `AnswerPayload` with `answer_text` field)
- Codebase inspection: `src/tool_errors.py` (line 57: `_is_provided`, line 67: `_validate_answer_text_xml_fields`)
- Codebase inspection: `src/tools_write.py` (line 112: `build_answer_payloads` call, line 115: `word_handler.write_answers`)
- Phase 5 verification report: All 13 truths verified, 250 tests passing
- Phase 5 research: Architecture patterns and pitfalls for the foundation layer

### Secondary (MEDIUM confidence)
- CLAUDE.md file size guidelines: 200 lines max per file. word_writer.py is at 182 lines currently.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all changes use existing Phase 5 functions at confirmed versions
- Architecture: HIGH -- single file change (word_writer.py), straightforward routing logic, reuses existing functions verbatim
- Pitfalls: HIGH -- all identified through direct codebase inspection; most are already mitigated by Phase 5 validation layer

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain, no external dependencies changing)
