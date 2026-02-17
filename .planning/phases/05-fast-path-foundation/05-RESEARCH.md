# Phase 5: Fast Path Foundation - Research

**Researched:** 2026-02-17
**Domain:** Pydantic model evolution, OOXML formatting extraction, batch validation design
**Confidence:** HIGH

## Summary

Phase 5 adds the `answer_text` field to `AnswerPayload`, exposes `extract_formatting_from_element()` as a public function, and implements batch validation that enforces exactly-one-of semantics. No write-path changes -- that is Phase 6.

The codebase is well-structured for this change. The `AnswerPayload` model (models.py line 126) currently has `insertion_xml: str` as a required field. The change to make both `insertion_xml` and `answer_text` optional (`None` default) is straightforward in Pydantic v2 (2.12.5, already installed). The validation logic lives in `tool_errors.py` (`_build_word_payloads` and `_build_relaxed_payloads`), which is the right place for the batch-level "reject all if any invalid" behavior. The `extract_formatting()` function in `xml_formatting.py` already does the heavy lifting; the new `extract_formatting_from_element()` is a thin wrapper that skips the string-to-element parse step.

**Primary recommendation:** Implement as three discrete changes: (1) model field changes in models.py, (2) new public function in xml_formatting.py, (3) validation logic in tool_errors.py. The batch validation error aggregation belongs in tool_errors.py, not in a Pydantic model_validator, because the error messages need per-answer context (pair_id + index) that model-level validators cannot provide.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- When an agent provides BOTH `answer_text` and `insertion_xml` on the same answer object, **reject with error** -- do not silently prefer one field
- Error message should suggest which field to use: "Use `answer_text` for plain text answers, `insertion_xml` for structured OOXML. Don't provide both."
- In a mixed-mode `write_answers` call (some answers use `answer_text`, others use `insertion_xml`), validation is per-answer
- However, if ANY answer is invalid, **reject the entire batch before writing** -- no partial writes
- Error lists ALL invalid answers, not just the first one
- Empty string (`""`) = **not provided**
- Whitespace-only string (`"   "`) = **not provided** (strip before checking)
- Same strip-check logic applies to both `answer_text` and `insertion_xml` -- consistent behavior
- Pydantic model defaults changed from empty string to **`None`** -- `None` means "not provided", makes intent unambiguous
- Validation rule: exactly one of `answer_text` or `insertion_xml` must be non-None and non-empty after stripping
- Error messages list ALL invalid answers in the batch, not just the first
- Each invalid answer referenced by **both pair_id and position index**: e.g. "Answer 'q3' (index 2): ..."
- Distinct error messages for the two failure modes:
  - Neither provided: "Neither `answer_text` nor `insertion_xml` provided. Use `answer_text` for plain text answers, `insertion_xml` for structured OOXML."
  - Both provided: "Both `answer_text` and `insertion_xml` provided -- use one, not both. Use `answer_text` for plain text, `insertion_xml` for structured OOXML."
- Guidance included in error messages to help agents self-correct

### Claude's Discretion
- Exact Pydantic validator implementation (model_validator vs field_validator)
- `extract_formatting_from_element()` return type and internal structure
- Test organization and fixture design
- How to structure the validation error aggregation

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FAST-04 | Validation rejects answers with neither answer_text nor insertion_xml, with a clear error message | Batch validation in `tool_errors.py` collects all errors before raising. Error messages use locked wording from CONTEXT.md. The `_is_provided()` helper strips whitespace and checks for None. |
| FAST-05 | `extract_formatting_from_element()` exposed as public function in xml_formatting.py | New function reuses existing `_find_run_properties`, `_extract_font_properties`, `_extract_size_and_color`, `_extract_style_properties` internals. Returns same `dict` as `extract_formatting()`. Re-exported through `xml_utils.py` barrel. |
| COMPAT-01 | Existing agents using insertion_xml continue working with zero changes | All 234 existing tests pass. The `insertion_xml` field changes from `str` (required) to `Optional[str] = None`, but all existing callers provide it explicitly. The `_build_word_payloads` validation now accepts `insertion_xml`-only answers. |
| COMPAT-02 | Mixed answer_text and insertion_xml answers work in the same write_answers call | Per-answer validation: each answer independently checked for exactly-one-of. A batch with some `answer_text` and some `insertion_xml` answers passes validation as long as each individual answer has exactly one. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 | Data models, Optional field defaults, validation | Already in use; v2 `model_validator` and `Optional[str] = None` are idiomatic |
| lxml | 6.0.2 | OOXML element manipulation | Already in use; `extract_formatting_from_element()` takes `etree._Element` directly |
| pytest | 9.0.2 | Test framework | Already in use; 234 existing tests |

### Supporting
No new libraries needed. All changes use existing dependencies.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `model_validator` on AnswerPayload | Validation in `tool_errors.py` | model_validator cannot reference batch context (pair_id + index in error messages). tool_errors.py is the right place. **Recommendation: tool_errors.py** |
| Pydantic `field_validator` | model_validator | field_validator runs per-field, cannot cross-check two fields. model_validator can, but batch context is still missing. **Recommendation: neither -- use tool_errors.py** |

## Architecture Patterns

### Recommended Approach

The changes touch 4 files, each with a focused responsibility:

```
src/
├── models.py                    # AnswerPayload field changes (None defaults)
├── xml_formatting.py            # New extract_formatting_from_element() function
├── xml_utils.py                 # Re-export new function
└── tool_errors.py               # Batch validation logic (_is_provided, error aggregation)
```

### Pattern 1: Optional Fields with None Default (Pydantic v2)

**What:** Change `insertion_xml: str` to `insertion_xml: str | None = None` and add `answer_text: str | None = None`. Both default to `None` (not provided).

**When to use:** When a field is truly optional and "not provided" is a distinct state from "empty string".

**Example:**
```python
# Source: Verified against pydantic 2.12.5 behavior
class AnswerPayload(BaseModel):
    pair_id: str
    xpath: str
    insertion_xml: str | None = None   # was: insertion_xml: str (required)
    answer_text: str | None = None     # NEW
    mode: InsertionMode
    confidence: Confidence = Confidence.KNOWN
```

**Critical detail:** Changing `insertion_xml` from required `str` to `Optional[str] = None` is backward-compatible. All existing callers pass `insertion_xml` explicitly (verified: 234 tests, all `AnswerPayload(... insertion_xml=..., ...)` calls provide the field). Agents sending JSON dicts will continue to work because `insertion_xml` is still accepted.

### Pattern 2: Batch Validation with Error Aggregation

**What:** Validate all answers first, collect all errors, then raise a single ValueError listing all invalid answers. No partial writes.

**When to use:** When the user decision requires all-or-nothing batch behavior.

**Example:**
```python
# In tool_errors.py
def _is_provided(value: str | None) -> bool:
    """Check if a field value counts as 'provided' per CONTEXT.md rules."""
    return value is not None and value.strip() != ""

def _validate_answer_fields(answer: dict, index: int) -> str | None:
    """Return error message if answer has invalid field combination, else None."""
    pair_id = answer.get("pair_id", f"<unknown at index {index}>")
    has_text = _is_provided(answer.get("answer_text"))
    has_xml = _is_provided(answer.get("insertion_xml"))

    if has_text and has_xml:
        return (
            f"Answer '{pair_id}' (index {index}): "
            "Both `answer_text` and `insertion_xml` provided "
            "-- use one, not both. Use `answer_text` for plain text, "
            "`insertion_xml` for structured OOXML."
        )
    if not has_text and not has_xml:
        return (
            f"Answer '{pair_id}' (index {index}): "
            "Neither `answer_text` nor `insertion_xml` provided. "
            "Use `answer_text` for plain text answers, "
            "`insertion_xml` for structured OOXML."
        )
    return None
```

### Pattern 3: Extract Formatting from Element (No Parse Step)

**What:** A public function that takes an `lxml.etree._Element` directly and returns the same formatting dict as `extract_formatting()`, skipping the XML string parse.

**When to use:** When the caller already has a parsed element (e.g., Phase 6's write path which will resolve the target element by XPath).

**Example:**
```python
# In xml_formatting.py
def extract_formatting_from_element(elem: etree._Element) -> dict:
    """Extract run-level formatting from a parsed lxml element.

    Same as extract_formatting() but takes a pre-parsed element instead
    of an XML string. Used by the fast path in write_answers to avoid
    re-parsing elements that were already resolved by XPath.
    """
    rpr = _find_run_properties(elem)
    if rpr is None:
        return {}

    formatting: dict = {}
    formatting.update(_extract_font_properties(rpr))
    formatting.update(_extract_size_and_color(rpr))
    formatting.update(_extract_style_properties(rpr))
    return formatting
```

### Anti-Patterns to Avoid

- **Pydantic model_validator for batch context:** A model_validator on `AnswerPayload` runs per-instance. It cannot know the answer's index in the batch or aggregate errors across the batch. The validation belongs in `tool_errors.py` where the full list context is available.
- **Silent field preference:** Do NOT silently prefer one field over another when both are provided. The user decision explicitly requires rejection with an error.
- **Short-circuit on first error:** The user decision explicitly requires ALL invalid answers to be reported, not just the first.
- **Partial writes:** If any answer in the batch is invalid, the entire batch must be rejected before any writes occur.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Is this field provided?" check | Inline `if value and value.strip()` scattered everywhere | A single `_is_provided(value)` helper | Centralized, testable, consistent behavior for None/""/whitespace |
| Formatting extraction from elements | Duplicate logic from `extract_formatting` | `extract_formatting_from_element()` that reuses the same private helpers | Single source of truth; `extract_formatting()` refactored to call it internally |

**Key insight:** The existing `extract_formatting()` should be refactored to delegate to `extract_formatting_from_element()` so there is exactly one code path for formatting extraction. This avoids logic drift.

## Common Pitfalls

### Pitfall 1: Breaking Existing Tests by Changing Field from Required to Optional
**What goes wrong:** Changing `insertion_xml: str` (required) to `insertion_xml: str | None = None` (optional) could break tests that pass empty string `""` and expect it to be valid.
**Why it happens:** The semantics change: `""` used to be a valid value, now it means "not provided" per the user decision.
**How to avoid:** The tool_errors.py validation layer (not the model) enforces the "strip then check" rule. The Pydantic model itself is permissive (accepts any string or None). Validation happens in `_build_word_payloads` and `_build_relaxed_payloads`.
**Warning signs:** Tests that construct `AnswerPayload(insertion_xml="", ...)` -- these would need `insertion_xml=None` or a real value. Checked: no existing tests pass empty string for `insertion_xml`. All pass real content.

### Pitfall 2: Forgetting to Update _ALL_KNOWN_FIELDS in tool_errors.py
**What goes wrong:** If `answer_text` is added to `AnswerPayload` but not to `_ALL_KNOWN_FIELDS`, the "unexpected fields" check in `_build_word_payloads` rejects any dict containing `answer_text`.
**Why it happens:** The allowlist is maintained separately from the model.
**How to avoid:** Update `_WORD_OPTIONAL` (or `_ALL_KNOWN_FIELDS`) to include `"answer_text"`. Also update `_WORD_REQUIRED` to no longer require `insertion_xml` unconditionally -- it is now conditionally required (one of two must be present).
**Warning signs:** Agents sending `answer_text` get "Unexpected fields: ['answer_text']" error.

### Pitfall 3: Breaking the Relaxed Payload Path (Excel/PDF)
**What goes wrong:** Excel and PDF already use `insertion_xml` as a plain-text value field (not actual XML). The `_build_relaxed_payloads` function in tool_errors.py uses `a.get("insertion_xml") or a.get("value", "")`. Adding `answer_text` must not break this path.
**Why it happens:** The relaxed path has different semantics -- it maps `value` to `insertion_xml` for backward compat.
**How to avoid:** For Excel/PDF in the relaxed path, `answer_text` should be accepted as an alias for `insertion_xml`/`value`. The same exactly-one-of validation applies. But the relaxed path must still accept `value` as a key name.
**Warning signs:** Excel/PDF tests failing after model changes.

### Pitfall 4: Error Message Formatting with Missing pair_id
**What goes wrong:** If an answer dict is malformed and doesn't have a `pair_id`, the error message template `f"Answer '{pair_id}' (index {index})"` throws a KeyError.
**Why it happens:** The validation runs before pair_id existence is confirmed.
**How to avoid:** Use `answer.get("pair_id", "<missing>")` as the fallback.
**Warning signs:** Crash during validation of truly malformed input.

### Pitfall 5: Re-export Through xml_utils.py
**What goes wrong:** `extract_formatting_from_element` is created in xml_formatting.py but callers importing from `xml_utils` cannot access it.
**Why it happens:** xml_utils.py is a barrel re-export module. New public functions must be added there.
**How to avoid:** Add `extract_formatting_from_element` to the `from src.xml_formatting import (...)` block in xml_utils.py.
**Warning signs:** ImportError in Phase 6 when it tries to import from xml_utils.

## Code Examples

Verified patterns from the actual codebase:

### Current AnswerPayload Model (will change)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/models.py, line 126
class AnswerPayload(BaseModel):
    pair_id: str
    xpath: str            # Word/Excel/PDF target reference
    insertion_xml: str    # pre-built XML (Word) or plain value (Excel/PDF)
    mode: InsertionMode
    confidence: Confidence = Confidence.KNOWN
```

### New AnswerPayload Model (Phase 5 target)
```python
class AnswerPayload(BaseModel):
    pair_id: str
    xpath: str
    insertion_xml: str | None = None   # pre-built XML (Word) or plain value (Excel/PDF)
    answer_text: str | None = None     # plain text answer (fast path, Word only)
    mode: InsertionMode
    confidence: Confidence = Confidence.KNOWN
```

### Current extract_formatting() (string-based)
```python
# Source: /home/sarturko/vibe-legal-form-filler/src/xml_formatting.py, line 124
def extract_formatting(element_xml: str) -> dict:
    elem = _parse_element_xml(element_xml)
    rpr = _find_run_properties(elem)
    if rpr is None:
        return {}
    formatting: dict = {}
    formatting.update(_extract_font_properties(rpr))
    formatting.update(_extract_size_and_color(rpr))
    formatting.update(_extract_style_properties(rpr))
    return formatting
```

### New extract_formatting_from_element() (element-based)
```python
# To add in xml_formatting.py
def extract_formatting_from_element(elem: etree._Element) -> dict:
    """Extract run-level formatting from a parsed lxml element.

    Same as extract_formatting() but takes a pre-parsed element instead
    of an XML string. Used by the fast path in write_answers (Phase 6).
    """
    rpr = _find_run_properties(elem)
    if rpr is None:
        return {}
    formatting: dict = {}
    formatting.update(_extract_font_properties(rpr))
    formatting.update(_extract_size_and_color(rpr))
    formatting.update(_extract_style_properties(rpr))
    return formatting
```

### Refactored extract_formatting() delegating to new function
```python
def extract_formatting(element_xml: str) -> dict:
    """Extract run-level formatting from an OOXML element string.

    Parses the string, then delegates to extract_formatting_from_element().
    """
    elem = _parse_element_xml(element_xml)
    return extract_formatting_from_element(elem)
```

### Batch Validation Error Aggregation Pattern
```python
# In tool_errors.py
def _validate_answer_text_xml_fields(answer_dicts: list[dict]) -> None:
    """Validate answer_text/insertion_xml field rules across all answers.

    Collects ALL errors, then raises a single ValueError if any exist.
    Called before any writes to enforce all-or-nothing batch behavior.
    """
    errors: list[str] = []
    for i, a in enumerate(answer_dicts):
        pair_id = a.get("pair_id", "<missing>")
        has_text = _is_provided(a.get("answer_text"))
        has_xml = _is_provided(a.get("insertion_xml"))

        if has_text and has_xml:
            errors.append(
                f"Answer '{pair_id}' (index {i}): "
                "Both `answer_text` and `insertion_xml` provided "
                "-- use one, not both. Use `answer_text` for plain text, "
                "`insertion_xml` for structured OOXML."
            )
        elif not has_text and not has_xml:
            errors.append(
                f"Answer '{pair_id}' (index {i}): "
                "Neither `answer_text` nor `insertion_xml` provided. "
                "Use `answer_text` for plain text answers, "
                "`insertion_xml` for structured OOXML."
            )

    if errors:
        header = f"write_answers validation failed ({len(errors)} invalid answer(s)):\n"
        raise ValueError(header + "\n".join(errors))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `insertion_xml: str` (required) | `insertion_xml: str \| None = None` | Phase 5 | Backward-compatible: all callers already pass it explicitly |
| String-only formatting extraction | Both string and element entry points | Phase 5 | Phase 6 fast path avoids redundant string serialize/parse round-trip |
| Word requires all four fields | Word requires pair_id, xpath, mode + exactly one of insertion_xml/answer_text | Phase 5 | Agents can now pass plain text directly |

## Open Questions

1. **Should `extract_formatting()` delegate to `extract_formatting_from_element()` or remain separate?**
   - What we know: Both paths share identical logic. Delegation means one code path.
   - What's unclear: Whether the minimal indirection adds clarity or confusion.
   - Recommendation: **Delegate.** One code path eliminates logic drift risk. All existing tests for `extract_formatting()` also implicitly test the new function.

2. **Should the relaxed path (Excel/PDF) also enforce the new validation?**
   - What we know: Excel/PDF currently accept `insertion_xml` or `value` as plain-text content. They don't use `answer_text` semantically.
   - What's unclear: Whether adding `answer_text` support to the relaxed path is in Phase 5 scope.
   - Recommendation: **Yes, add to relaxed path.** The `answer_text` field on `AnswerPayload` applies to all file types. For Excel/PDF, `answer_text` would simply be an alias for the value. The exactly-one-of validation should apply universally. This ensures COMPAT-02 (mixed mode) works regardless of file type.

3. **How should `_build_word_payloads` change its "required fields" check?**
   - What we know: Currently `_WORD_REQUIRED = ("pair_id", "xpath", "insertion_xml", "mode")`. With answer_text, `insertion_xml` is no longer unconditionally required.
   - What's unclear: How to maintain the "required" check while allowing one-of-two.
   - Recommendation: Change `_WORD_REQUIRED` to `("pair_id", "xpath", "mode")` (always required). Add `"answer_text"` to `_ALL_KNOWN_FIELDS`. Run the exactly-one-of validation separately via `_validate_answer_text_xml_fields()`. This keeps the checks layered: (1) always-required fields present, (2) exactly-one-of content field present, (3) no unexpected fields, (4) valid enum values.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/models.py` (AnswerPayload definition, line 126)
- Codebase inspection: `src/xml_formatting.py` (extract_formatting implementation, line 124)
- Codebase inspection: `src/tool_errors.py` (_build_word_payloads, _build_relaxed_payloads)
- Codebase inspection: `src/xml_utils.py` (barrel re-exports)
- Codebase inspection: `src/tools_write.py` (write_answers tool, how payloads are consumed)
- Codebase inspection: `tests/test_word.py`, `tests/test_excel.py`, `tests/test_pdf.py` (all 234 tests, AnswerPayload usage patterns)
- Codebase inspection: `requirements.txt` (pydantic==2.12.5 confirmed)
- Pydantic v2.12.5 installed and verified: `Optional[str] = None` is the idiomatic pattern

### Secondary (MEDIUM confidence)
- Pydantic v2 documentation (from training data, cross-verified with installed version): `model_validator(mode='before')` and `field_validator` behavior confirmed

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all changes use existing libraries at confirmed versions
- Architecture: HIGH -- changes are localized to 4 files with clear boundaries, codebase patterns are well-established
- Pitfalls: HIGH -- all identified through direct codebase inspection, verified against actual test usage

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain, no external dependencies changing)
