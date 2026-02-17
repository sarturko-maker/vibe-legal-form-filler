# Phase 10: Verification Parity - Research

**Researched:** 2026-02-17
**Domain:** verify_output pair_id resolution, cross-check validation, response metadata
**Confidence:** HIGH

## Summary

Phase 10 extends the pair_id resolution pattern established in Phase 8 (for `write_answers`) to the `verify_output` tool, achieving parity so agents can use the same simplified identifiers for both writing and verifying. Currently, `verify_output` requires `xpath` as a mandatory field on every `ExpectedAnswer`, forcing agents to carry xpaths through the pipeline even when they only have pair_ids. After this phase, agents can call `verify_output` with just `{pair_id, expected_text}` and the server resolves the xpath automatically.

The implementation is a focused, low-risk change. Phase 8 already built the resolution infrastructure (`pair_id_resolver.py` with `resolve_pair_ids()`, `cross_check_xpaths()`, `resolve_if_needed()`). This phase reuses that exact infrastructure in the verification path. The total surface area is: one model change (`ExpectedAnswer.xpath` becomes optional), one validation function change (`validate_expected_answers` in `tool_errors.py`), one tool function change (`verify_output` in `tools_write.py`), and one response format addition (`resolved_from` metadata).

**Primary recommendation:** Follow the Phase 8 pattern exactly: make `xpath` optional on `ExpectedAnswer`, add resolution to `validate_expected_answers()` (or a new wrapper), and add `resolved_from` metadata to the response. Use the same `resolve_pair_ids()` and `cross_check_xpaths()` functions from `pair_id_resolver.py`. Handle Excel/PDF with the relaxed path (pair_id IS the xpath -- identity resolution).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VER-01 | `verify_output` accepts `pair_id` without `xpath` -- resolves from pair_id via re-extraction | Resolution infrastructure exists in `pair_id_resolver.py:36-64`. Same `resolve_pair_ids()` function used by `write_answers`. `ExpectedAnswer.xpath` must become `Optional[str] = None` in `models.py:173`. Validation in `tool_errors.py:394-426` must be updated to make xpath optional and resolve from pair_id when missing. |
| VER-02 | `verify_output` cross-checks xpath against pair_id resolution when both provided | `cross_check_xpaths()` already exists in `pair_id_resolver.py:117-141`. Same function, same pattern -- compare agent xpath vs resolved xpath, generate warning strings, use resolved xpath as authority. Warnings must appear in the `verify_output` response. |
</phase_requirements>

## Standard Stack

### Core

No new libraries needed. This phase uses only existing project dependencies.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | existing | Model optionality (`Optional[str] = None`) | Already used for all models; `ExpectedAnswer` is a Pydantic BaseModel |
| lxml | existing | Word re-extraction for pair_id resolution | Already used by `word_indexer.extract_structure_compact()` |
| openpyxl | existing | Excel re-extraction | Already used by `excel_indexer.extract_structure_compact()` |
| fitz (PyMuPDF) | existing | PDF re-extraction | Already used by `pdf_indexer.extract_structure_compact()` |

### Supporting

None needed -- this is extending an existing pattern to a second tool.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Re-extraction per verify call | Cache resolved xpaths from write_answers | Violates stateless design; verify may be called on a different document than was written; cache invalidation is hard |
| Adding resolution to validate_expected_answers | New wrapper function in tools_write.py | validate_expected_answers is already a validation wrapper; adding resolution keeps the pattern consistent with build_answer_payloads |
| Separate `resolved_from` per-answer field | Single resolution metadata on the response | Per-answer is more precise when some answers have xpath and others only have pair_id; consistent with the success criteria |

**Installation:**
No installation needed. All dependencies already present.

## Architecture Patterns

### Recommended Module Changes

```
src/
├── pair_id_resolver.py          # UNCHANGED: resolve_pair_ids, cross_check_xpaths already exist
├── models.py                    # MODIFIED: ExpectedAnswer.xpath becomes Optional[str] = None
├── tool_errors.py               # MODIFIED: validate_expected_answers handles optional xpath, resolves pair_id
├── tools_write.py               # MODIFIED: verify_output passes file_bytes to validation, adds metadata to response
├── handlers/word_verifier.py    # UNCHANGED: receives ExpectedAnswer with xpath already resolved
├── handlers/excel_verifier.py   # UNCHANGED: receives ExpectedAnswer with xpath already resolved
├── handlers/pdf_verifier.py     # UNCHANGED: receives ExpectedAnswer with xpath already resolved
```

### Pattern 1: Resolution at Validation Boundary (Mirror Phase 8)

**What:** Resolve pair_ids to xpaths in the validation/payload-building layer (`tool_errors.py`), before answers reach the handler-level verifiers. This is the same pattern Phase 8 used for `write_answers`.

**When to use:** Always -- this keeps the handler verifiers clean (they always receive fully resolved xpaths).

**How it works:**

```python
# In tool_errors.py -- validate_expected_answers with resolution
def validate_expected_answers(
    expected_answers: list[dict],
    ft: FileType | None = None,
    file_bytes: bytes | None = None,
) -> tuple[list[ExpectedAnswer], list[str]]:
    """Build ExpectedAnswer list, resolving pair_ids when xpath is missing.

    Returns (answers, warnings). Warnings from cross-check when both
    xpath and pair_id are provided.
    """
    # ... validation logic ...
    # ... resolution logic (same as write path) ...
    # ... cross-check logic ...
    return results, warnings
```

**Key insight:** The function signature change (adding `ft` and `file_bytes` params, returning a tuple) mirrors exactly what happened to `build_answer_payloads` in Phase 8. The handler verifiers never need to know about pair_id resolution -- they receive resolved `ExpectedAnswer` objects with valid xpaths.

### Pattern 2: Per-Answer Resolution Metadata

**What:** Track how each answer's xpath was obtained (from the agent directly, or resolved from pair_id) and include this in the response.

**When to use:** Required by success criterion 4: "verify_output response includes resolution metadata (resolved_from='pair_id' or 'xpath')".

**How it works:**

The `VerificationReport` response already contains `content_results` (per-answer) and `summary` (aggregate). The resolution metadata belongs at the per-answer level (`ContentResult`) since different answers may be resolved differently.

Option A: Add `resolved_from` to the `ContentResult` model.
Option B: Add `resolution_metadata` as a separate list in the response dict (parallel to content_results).
Option C: Add `resolved_from` as a top-level field on the response dict when resolution was used.

**Recommendation:** Option A -- add `resolved_from: str | None = None` to `ContentResult`. This is the most precise (per-answer), consistent with the success criteria, and cleanly serializes via `model_dump()`. The field defaults to `None` for backward compatibility (existing callers see no change). When resolution is used, it's set to `"pair_id"` for resolved answers and `"xpath"` for agent-provided xpaths.

### Pattern 3: Relaxed Path for Excel/PDF (Prior Decision 08-02)

**What:** For Excel and PDF, pair_id IS the xpath (identity mapping). No re-extraction needed.

**When to use:** When `file_type` is EXCEL or PDF and the answer has pair_id but no xpath.

**How it works:** Set `xpath = pair_id` directly. This is what `_build_relaxed_payloads` does for `write_answers` (line 361 of `tool_errors.py`). The same pattern applies here.

**Cross-check on relaxed path:** Per prior decision 08-02, cross-check warnings only fire on the Word path where xpath and pair_id are distinct identifier systems. On Excel/PDF, pair_id == xpath, so cross-check is trivially satisfied (or skipped).

### Anti-Patterns to Avoid

- **Duplicating resolution logic:** The `pair_id_resolver.py` module already has `resolve_pair_ids()` and `cross_check_xpaths()`. Do not reimplement these in `tool_errors.py`. Import and reuse.
- **Changing handler verifiers:** The `word_verifier.py`, `excel_verifier.py`, and `pdf_verifier.py` should NOT be modified. Resolution happens before they're called. They receive `ExpectedAnswer` objects with xpath already populated.
- **Making xpath optional at handler level:** The verifiers rely on `answer.xpath` being a valid string. The optionality is handled at the `tool_errors.py` validation layer. By the time the handler receives the `ExpectedAnswer`, xpath is always a string (resolved from pair_id if necessary).
- **Breaking the function signature without updating callers:** `validate_expected_answers` is called from `tools_write.py:225`. Its return type changes from `list[ExpectedAnswer]` to `tuple[list[ExpectedAnswer], list[str]]`. Update the call site.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| pair_id to xpath mapping | Custom resolution logic | `pair_id_resolver.resolve_pair_ids()` | Already built and tested in Phase 8; handles Word/Excel/PDF |
| Cross-check logic | Custom comparison | `pair_id_resolver.cross_check_xpaths()` | Already built and tested in Phase 8; generates formatted warnings |
| Resolution triggering | Custom needs-resolution detection | Same conditional pattern from `pair_id_resolver.resolve_if_needed()` | Already handles the "only when needed" optimization |

**Key insight:** Phase 8 built the entire resolution infrastructure generically. This phase is wiring it into a second consumer (`verify_output`). Zero new resolution logic is needed.

## Common Pitfalls

### Pitfall 1: Breaking validate_expected_answers Return Type

**What goes wrong:** `validate_expected_answers` currently returns `list[ExpectedAnswer]`. Changing it to return `tuple[list[ExpectedAnswer], list[str]]` (to include warnings) breaks the call in `tools_write.py:225` if not updated simultaneously.

**Why it happens:** The function signature change mirrors what happened to `build_answer_payloads` in Phase 8, but the caller in `tools_write.py` does `answers = validate_expected_answers(expected_answers)` -- no tuple unpacking.

**How to avoid:** Update both the function and its caller in the same commit. Change `tools_write.py:225` from `answers = validate_expected_answers(expected_answers)` to `answers, warnings = validate_expected_answers(expected_answers, ft, raw)`.

**Warning signs:** TypeError: cannot unpack non-sequence list.

### Pitfall 2: ExpectedAnswer.xpath Still Required at Model Level

**What goes wrong:** If `ExpectedAnswer.xpath` is made `Optional[str] = None` at the model level but the validation in `tool_errors.py` still lists "xpath" in `_EXPECTED_REQUIRED`, then agents sending pair_id-only answers will hit a validation error BEFORE resolution can run.

**Why it happens:** The validation check runs before resolution. `_EXPECTED_REQUIRED = ("pair_id", "xpath", "expected_text")` rejects answers without xpath immediately.

**How to avoid:** Remove `"xpath"` from `_EXPECTED_REQUIRED`. Instead, validate conditionally: if no xpath AND no pair_id, raise error. If no xpath but has pair_id, proceed to resolution. If resolution fails (pair_id not found in document), raise a clear error at that point.

**Warning signs:** "Missing required: ['xpath']" error when agent sends pair_id-only answers.

### Pitfall 3: Resolution Needs file_bytes -- But verify_output May Not Have Them

**What goes wrong:** Resolution calls `extract_structure_compact(file_bytes)`. The `verify_output` tool already has `raw` bytes from `resolve_file_for_tool()`. But `validate_expected_answers()` currently doesn't receive them.

**Why it happens:** The current `validate_expected_answers` signature takes only `list[dict]`. Resolution requires `file_bytes` and `file_type`.

**How to avoid:** Add `file_bytes` and `file_type` as optional parameters to `validate_expected_answers`. When both are None, resolution is skipped and xpath remains required (backward compatible). This mirrors the `build_answer_payloads(answer_dicts, ft, file_bytes)` pattern.

**Warning signs:** "pair_id could not be resolved" error even when pair_id is valid, because file_bytes wasn't passed through.

### Pitfall 4: PDF Verifier Uses Sequential F-ID Counter

**What goes wrong:** The PDF verifier (`pdf_verifier.py:93-109`) builds its value index by iterating pages and widgets in order, assigning F1, F2, F3, etc. This is the same deterministic order used by the indexer. If pair_id resolution produces a different F-ID mapping than the verifier's counter, content checks will fail.

**Why it happens:** The F-ID assignment depends on widget iteration order. If the indexer and verifier iterate differently, IDs won't match.

**How to avoid:** The current code already handles this correctly -- both the indexer and verifier use the same `for page_num... for widget...` iteration order. The resolved xpath for PDF is the native field name (from `id_to_xpath`), but the verifier currently uses F-IDs (not field names). This is a potential mismatch.

**Actually, looking more carefully:** `pdf_indexer.extract_structure_compact()` returns `id_to_xpath` mapping `F1 -> "full_name"` (field name), not `F1 -> F1`. But the PDF verifier's `_build_value_index()` builds a `field_id -> value` mapping using F-IDs. And `answer.xpath` is currently an F-ID like "F1".

For pair_id-only verification on PDF: if we resolve `pair_id="F1"` via `resolve_pair_ids`, we get `xpath="full_name"` (the native field name). But the verifier expects `answer.xpath` to be "F1" (which it uses to look up in its own F-ID-indexed map). This creates a mismatch.

**Resolution for PDF:** On the relaxed path (Excel/PDF), pair_id IS the element ID. For PDF verification, the identity mapping should be used: `xpath = pair_id = "F1"`. The relaxed path should NOT call `resolve_pair_ids()` for PDF/Excel -- it should set `xpath = pair_id` directly, same as `_build_relaxed_payloads` does for `write_answers`. This matches prior decision 08-02.

**Warning signs:** PDF verification returns "missing" for all answers when pair_id resolution is used.

### Pitfall 5: Response Metadata Must Be Additive-Only

**What goes wrong:** Adding `resolved_from` to `ContentResult` or `warnings` to the response could break agents that parse the response strictly.

**Why it happens:** Some agents may destructure `verify_output` responses with exact key matching.

**How to avoid:** `resolved_from` is an Optional field with default None on a Pydantic model -- `model_dump()` includes it but with value None (existing behavior unchanged). `warnings` is only added to the response dict when non-empty (same pattern as write_answers). No breaking changes.

**Warning signs:** Agent errors on unexpected keys in verification response.

## Code Examples

### Example 1: ExpectedAnswer Model Change

```python
# In models.py -- make xpath optional
class ExpectedAnswer(BaseModel):
    pair_id: str
    xpath: str | None = None          # Optional when pair_id is provided
    expected_text: str
    confidence: Confidence = Confidence.KNOWN
```

### Example 2: ContentResult with Resolution Metadata

```python
# In models.py -- add resolved_from to ContentResult
class ContentResult(BaseModel):
    pair_id: str
    status: ContentStatus
    expected: str
    actual: str
    resolved_from: str | None = None  # "pair_id" or "xpath" or None
```

### Example 3: Updated validate_expected_answers

```python
# In tool_errors.py -- resolution-aware validation
def validate_expected_answers(
    expected_answers: list[dict],
    ft: FileType | None = None,
    file_bytes: bytes | None = None,
) -> tuple[list[ExpectedAnswer], list[str]]:
    """Build ExpectedAnswer list, resolving pair_ids when xpath is missing.

    Returns (answers, warnings). Warnings from cross-check.
    """
    # Check required fields (pair_id and expected_text always required)
    for i, a in enumerate(expected_answers):
        if "pair_id" not in a or "expected_text" not in a:
            # ... rich error ...

    # Resolve pair_ids when xpath is missing
    needs_resolution = any(
        not a.get("xpath") and a.get("pair_id")
        for a in expected_answers
    )
    needs_cross_check = any(
        a.get("xpath") and a.get("pair_id")
        for a in expected_answers
    )

    resolved = {}
    warnings = []
    if (needs_resolution or needs_cross_check) and file_bytes and ft:
        pair_ids = [a["pair_id"] for a in expected_answers if a.get("pair_id")]
        if ft in (FileType.EXCEL, FileType.PDF):
            # Relaxed path: pair_id IS the xpath
            resolved = {pid: pid for pid in pair_ids}
        else:
            # Word path: resolve via re-extraction
            from src.pair_id_resolver import resolve_pair_ids
            resolved = resolve_pair_ids(file_bytes, ft, pair_ids)

        if ft == FileType.WORD:
            from src.pair_id_resolver import cross_check_xpaths
            warnings = cross_check_xpaths(expected_answers, resolved)

    # Build ExpectedAnswer objects with resolved xpaths
    results = []
    for i, a in enumerate(expected_answers):
        xpath = a.get("xpath")
        resolved_from = None
        if not xpath and a.get("pair_id"):
            xpath = resolved.get(a["pair_id"])
            if not xpath and ft in (FileType.EXCEL, FileType.PDF):
                xpath = a["pair_id"]  # Identity fallback
            resolved_from = "pair_id"
        elif xpath:
            resolved_from = "xpath"
            if a.get("pair_id") in resolved and resolved[a["pair_id"]] != xpath:
                xpath = resolved[a["pair_id"]]  # pair_id is authority
                resolved_from = "pair_id"

        if not xpath:
            raise ValueError(
                f"Expected answer '{a.get('pair_id')}' (index {i}): "
                f"No xpath provided and pair_id could not be resolved."
            )

        results.append(ExpectedAnswer(
            pair_id=a["pair_id"],
            xpath=xpath,
            expected_text=a["expected_text"],
            **({"confidence": Confidence(a["confidence"])} if "confidence" in a else {}),
        ))
    return results, warnings
```

### Example 4: Updated verify_output Tool

```python
# In tools_write.py -- pass file_bytes and ft, handle warnings and metadata
@mcp.tool()
def verify_output(
    expected_answers: list[dict],
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    raw, ft = resolve_file_for_tool(
        "verify_output",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )
    answers, warnings = validate_expected_answers(expected_answers, ft, raw)

    if ft == FileType.WORD:
        result = word_verify_output(raw, answers).model_dump()
    elif ft == FileType.EXCEL:
        result = excel_verify_output(raw, answers).model_dump()
    elif ft == FileType.PDF:
        result = pdf_verify_output(raw, answers).model_dump()
    else:
        raise NotImplementedError(...)

    # Add resolution metadata to content_results
    for i, a in enumerate(answers):
        if i < len(result["content_results"]):
            result["content_results"][i]["resolved_from"] = ...

    if warnings:
        result["warnings"] = warnings

    return result
```

### Example 5: Resolution Metadata Tracking

```python
# Track resolved_from alongside ExpectedAnswer during validation
# Option: Return it as a parallel list from validate_expected_answers
def validate_expected_answers(
    expected_answers: list[dict],
    ft: FileType | None = None,
    file_bytes: bytes | None = None,
) -> tuple[list[ExpectedAnswer], list[str], list[str | None]]:
    """Returns (answers, warnings, resolved_from_list)."""
    # ... resolution logic ...
    resolved_from_list = []  # parallel to results
    for i, a in enumerate(expected_answers):
        if ... resolved from pair_id ...:
            resolved_from_list.append("pair_id")
        else:
            resolved_from_list.append("xpath")
    return results, warnings, resolved_from_list
```

**Alternative approach:** Instead of a parallel list, add `resolved_from` directly to `ContentResult` in `models.py`. This is cleaner since the metadata travels with the result naturally.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Agent provides xpath for every expected_answer | (This phase) Server resolves xpath from pair_id | v2.1, Phase 10 | Eliminates agent xpath bookkeeping for verification |
| verify_output response has no resolution metadata | (This phase) Response includes resolved_from per-answer | v2.1, Phase 10 | Agent can see how each answer was resolved for debugging |
| No cross-check on verify_output | (This phase) Cross-check warns on mismatch | v2.1, Phase 10 | Consistent with write_answers behavior |

**After this phase, minimal verify_output payload:**
```json
{
    "pair_id": "T1-R2-C2",
    "expected_text": "Acme Corporation"
}
```

(vs current minimum):
```json
{
    "pair_id": "T1-R2-C2",
    "xpath": "./w:tbl[1]/w:tr[2]/w:tc[2]",
    "expected_text": "Acme Corporation"
}
```

## Open Questions

1. **Should resolved_from live on ContentResult or be tracked separately?**
   - What we know: Success criterion 4 says "verify_output response includes resolution metadata (resolved_from='pair_id' or 'xpath')". `ContentResult` is the per-answer result model. Adding a field there is the cleanest approach.
   - What's unclear: Whether adding an Optional field to `ContentResult` breaks any downstream consumers.
   - Recommendation: Add `resolved_from: str | None = None` to `ContentResult`. Pydantic serializes it as `null` when not set, which is backward compatible. The field is only populated when Phase 10 resolution is used.

2. **Should validate_expected_answers return type change to tuple, or should a new function be created?**
   - What we know: Phase 8 changed `build_answer_payloads` from returning `list[AnswerPayload]` to `tuple[list[AnswerPayload], list[str]]`. Same pattern applies.
   - What's unclear: Whether to modify the existing function or create a `validate_and_resolve_expected_answers` wrapper.
   - Recommendation: Modify the existing function. Add `ft` and `file_bytes` as optional params with `None` defaults. When both are None, behaves identically to current (xpath required, no resolution). This is backward compatible and matches the Phase 8 pattern exactly.

3. **How should resolved_from be populated in the response?**
   - What we know: validate_expected_answers knows which answers were resolved. But the handler verifiers produce ContentResult objects without resolved_from.
   - What's unclear: Where to inject the resolved_from value -- before or after the handler call.
   - Recommendation: Track resolved_from as a parallel list during validation. After the handler returns ContentResult objects, inject resolved_from into each result in `tools_write.py`. This keeps handlers untouched and injection is a simple post-processing step.

4. **Should the tool docstring and USAGE example be updated?**
   - What we know: The current USAGE example in tool_errors.py shows: `verify_output(file_path="filled.docx", expected_answers=[{"pair_id": "q1", "xpath": "/w:body/...", "expected_text": "Acme Corp"}])`.
   - What's unclear: Whether to update this in Phase 10 or defer to Phase 11 (Documentation & QA).
   - Recommendation: Update the USAGE example and docstring in Phase 10 since the tool behavior is changing. Phase 11 handles CLAUDE.md and broader documentation, but the tool's own docstring should always be accurate.

## Sources

### Primary (HIGH confidence)

- **Codebase analysis**: Direct reading of all source files. All findings verified against actual code.
  - `src/pair_id_resolver.py` -- Resolution infrastructure (resolve_pair_ids, cross_check_xpaths, resolve_if_needed)
  - `src/models.py` -- Current ExpectedAnswer (xpath required, line 173) and ContentResult (no resolved_from, line 178)
  - `src/tool_errors.py` -- Current validate_expected_answers (lines 389-426, _EXPECTED_REQUIRED includes "xpath")
  - `src/tools_write.py` -- Current verify_output tool (lines 204-236)
  - `src/handlers/word_verifier.py` -- Word verifier (uses answer.xpath for XPath query)
  - `src/handlers/excel_verifier.py` -- Excel verifier (uses answer.xpath as cell_id)
  - `src/handlers/pdf_verifier.py` -- PDF verifier (uses answer.xpath as F-ID)
  - `src/verification.py` -- Shared verification helpers (build_verification_summary)
  - `tests/test_word_verifier.py` -- Existing verifier tests (211 lines, 6 test classes)
  - `tests/test_pair_id_resolver.py` -- Resolution tests (139 lines, 8 tests)
  - `tests/test_resolution.py` -- E2E resolution tests (175 lines, 6 tests)
- **Planning documents**: Phase 8 RESEARCH.md, Phase 8 VERIFICATION.md (resolution infrastructure confirmed complete)
- **Requirements**: REQUIREMENTS.md (VER-01, VER-02 defined), ROADMAP.md (Phase 10 success criteria)

### Secondary (MEDIUM confidence)

None needed -- all findings from direct codebase analysis.

### Tertiary (LOW confidence)

None -- all findings are from direct codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing libraries, all existing patterns
- Architecture: HIGH -- mirrors Phase 8 pattern exactly, all touchpoints identified from code reading
- Pitfalls: HIGH -- identified from direct code analysis, especially the PDF F-ID vs field name mismatch (Pitfall 4) which is the most subtle risk

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable -- internal codebase, no external API changes expected)
