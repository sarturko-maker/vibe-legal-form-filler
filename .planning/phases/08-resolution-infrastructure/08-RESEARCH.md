# Phase 8: Resolution Infrastructure - Research

**Researched:** 2026-02-17
**Domain:** Server-side pair_id-to-xpath resolution, Pydantic model optionality, cross-check validation
**Confidence:** HIGH

## Summary

Phase 8 makes `xpath` and `mode` optional in `AnswerPayload` when `answer_text` is provided, by resolving `pair_id` to an xpath via re-extraction of the compact structure. This is a purely internal server change -- no new libraries, no external dependencies, no architectural shifts. The entire implementation touches 3-4 existing files and adds one small new module.

The key insight from studying the codebase: the resolution logic already exists. `word_location_validator.py` already calls `extract_structure_compact()` to get `id_to_xpath` and looks up xpaths by element ID (line 64). The only new work is (1) lifting that resolution into the `write_answers` path, (2) making `xpath` and `mode` optional on `AnswerPayload`, and (3) adding cross-check logic when both are provided.

**Primary recommendation:** Create a small `pair_id_resolver.py` module that wraps `extract_structure_compact()` and returns `id_to_xpath` for each file type. Call it from `tools_write.py` (or `tool_errors.py`) during payload construction when `xpath` is missing. Keep the existing validation strict for `insertion_xml` answers (which still require `xpath` and `mode`).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ERG-03 | `xpath` is optional in `AnswerPayload` when `answer_text` is provided -- server resolves from `pair_id` via id_to_xpath re-extraction | Resolution logic exists in `word_location_validator.py` lines 60-65. Word uses `word_indexer.extract_structure_compact()`, Excel uses identity map (cell_id IS the xpath), PDF uses `pdf_indexer.extract_structure_compact()`. New resolver module wraps these three paths. |
| ERG-04 | `mode` defaults to `replace_content` when `answer_text` is provided and mode is omitted | `_build_relaxed_payloads()` in `tool_errors.py` (line 280) already defaults mode to `replace_content` for Excel/PDF. Same pattern applies to Word's `_build_word_payloads()`. |
| ERG-05 | When both `xpath` and `pair_id` are provided, server cross-checks and warns on mismatch (pair_id is authority) | Cross-check is a simple dict lookup after resolution. Warning must be non-blocking (included in response metadata, not raised as error). Current `write_answers` returns `dict` (line 146 of `tools_write.py`), so adding a `warnings` key is straightforward. |
</phase_requirements>

## Standard Stack

### Core

No new libraries needed. This phase uses only existing project dependencies.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | existing | Model optionality (Optional fields) | Already used for all models |
| lxml | existing | XML parsing for Word re-extraction | Already used throughout |
| openpyxl | existing | Excel re-extraction | Already used for Excel handler |
| fitz (PyMuPDF) | existing | PDF re-extraction | Already used for PDF handler |

### Supporting

None needed -- this is a refactoring/extension phase, not a new capability.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Re-extraction per write call | Cache id_to_xpath in module-level dict | Violates stateless design constraint; cache invalidation is hard; re-extraction is fast (~10ms for typical docx) |
| Separate resolver module | Inline resolution in tool_errors.py | Resolver module is cleaner separation of concerns, testable in isolation, and keeps tool_errors.py focused on validation |
| Warning in response dict | Logging-only (no response change) | Agents need to see warnings to debug issues; logging alone is invisible to the agent |

**Installation:**
No installation needed. All dependencies already present.

## Architecture Patterns

### Recommended Module Structure

```
src/
├── pair_id_resolver.py       # NEW: resolve_pair_ids(file_bytes, file_type, pair_ids) -> dict[str, str]
├── models.py                 # MODIFIED: xpath and mode become Optional on AnswerPayload
├── tool_errors.py            # MODIFIED: _build_word_payloads calls resolver when xpath missing
├── tools_write.py            # MODIFIED: pass file_bytes/file_type to payload builder, add warnings to response
```

### Pattern 1: Resolution as Pre-Processing Step

**What:** Before building AnswerPayloads, check which answers need xpath resolution. If any do, call the resolver once (not per-answer) and populate the missing xpaths.

**When to use:** Always -- this is the core pattern for this phase.

**How it works:**

```python
# In pair_id_resolver.py
def resolve_pair_ids(
    file_bytes: bytes,
    file_type: FileType,
    pair_ids: list[str],
) -> dict[str, str]:
    """Resolve pair_ids to xpaths via compact re-extraction.

    Returns a dict mapping pair_id -> xpath. Missing pair_ids
    are omitted from the result (caller must check).
    """
    if file_type == FileType.WORD:
        from src.handlers.word_indexer import extract_structure_compact
        compact = extract_structure_compact(file_bytes)
    elif file_type == FileType.EXCEL:
        from src.handlers.excel_indexer import extract_structure_compact
        compact = extract_structure_compact(file_bytes)
    elif file_type == FileType.PDF:
        from src.handlers.pdf_indexer import extract_structure_compact
        compact = extract_structure_compact(file_bytes)
    else:
        return {}

    return {
        pid: compact.id_to_xpath[pid]
        for pid in pair_ids
        if pid in compact.id_to_xpath
    }
```

### Pattern 2: Cross-Check as Post-Resolution Warning

**What:** After resolving pair_ids, compare resolved xpaths with agent-provided xpaths. If they differ, add a warning but use the pair_id-resolved xpath (pair_id is authority).

**When to use:** When both xpath and pair_id are provided in the same answer.

**How it works:**

```python
# In pair_id_resolver.py
def cross_check_xpaths(
    answers: list[dict],
    resolved: dict[str, str],
) -> list[str]:
    """Compare agent-provided xpaths against resolved xpaths.

    Returns a list of warning strings for mismatches.
    pair_id resolution takes precedence (warnings only).
    """
    warnings = []
    for a in answers:
        pair_id = a.get("pair_id", "")
        agent_xpath = a.get("xpath", "")
        resolved_xpath = resolved.get(pair_id, "")
        if agent_xpath and resolved_xpath and agent_xpath != resolved_xpath:
            warnings.append(
                f"pair_id '{pair_id}': agent xpath '{agent_xpath}' "
                f"differs from resolved xpath '{resolved_xpath}' "
                f"-- using resolved (pair_id is authority)"
            )
    return warnings
```

### Pattern 3: Conditional Resolution (Only When Needed)

**What:** Only call re-extraction if at least one answer is missing an xpath. This avoids the performance cost when all xpaths are already provided.

**When to use:** Always -- avoids unnecessary re-extraction for backward-compatible calls.

**How it works:**

```python
# In tool_errors.py or tools_write.py
needs_resolution = any(
    not a.get("xpath") and a.get("answer_text")
    for a in answer_dicts
)
needs_cross_check = any(
    a.get("xpath") and a.get("pair_id")
    for a in answer_dicts
)

if needs_resolution or needs_cross_check:
    pair_ids = [a["pair_id"] for a in answer_dicts]
    resolved = resolve_pair_ids(file_bytes, ft, pair_ids)
```

### Anti-Patterns to Avoid

- **Caching id_to_xpath across requests:** The server is stateless by design. Each `write_answers` call must resolve independently. Caching violates the core design constraint and introduces cache invalidation complexity.
- **Raising errors for cross-check mismatches:** The requirement is explicit -- mismatches produce warnings, not errors. pair_id is authority. Blocking writes on mismatch would be overly strict.
- **Resolving per-answer instead of per-call:** Calling `extract_structure_compact()` once per answer (N times for N answers) would be wasteful. Extract once, look up N times.
- **Changing the existing insertion_xml path:** Only `answer_text` answers get optional xpath/mode. The `insertion_xml` path still requires explicit xpath and mode because the agent already did the work.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| pair_id to xpath mapping | Custom XML walking | `extract_structure_compact()` from existing indexers | Already battle-tested across 281 tests; produces the exact same id_to_xpath the agent originally received |
| Pydantic optional fields | Manual None checks everywhere | Pydantic `Optional[str] = None` with validators | Pydantic handles serialization, validation, and defaults automatically |
| Warning aggregation | Ad-hoc string building | Simple list of warning strings returned in response dict | Matches the preview/dry_run pattern already in use |

**Key insight:** The resolution infrastructure is 95% already built. The `extract_structure_compact` → `id_to_xpath` pipeline is the core of the compact extraction feature (Phase 0 of the project). This phase is wiring it into the write path.

## Common Pitfalls

### Pitfall 1: Breaking Backward Compatibility on AnswerPayload

**What goes wrong:** Making `xpath` fully optional on `AnswerPayload` breaks the `insertion_xml` path which genuinely needs it (the server cannot know where to insert pre-built XML without an xpath).

**Why it happens:** Overly aggressive model relaxation -- making fields optional without conditional constraints.

**How to avoid:** Keep `xpath` required at the Pydantic model level. Handle optionality in `_build_word_payloads()` where the context (answer_text vs insertion_xml, file_bytes available) makes the decision clear. Alternatively, make xpath `Optional[str] = None` on the model but validate in `_build_word_payloads()` that insertion_xml answers always have xpath.

**Warning signs:** Tests for insertion_xml-based writes start failing.

### Pitfall 2: Re-Extraction Performance for Large Documents

**What goes wrong:** `extract_structure_compact()` parses the entire docx, walks all tables and paragraphs. For a 100-table document, this adds latency to every `write_answers` call.

**Why it happens:** Re-extraction is inherently non-free. The decision to use stateless resolution accepted this cost.

**How to avoid:** Only re-extract when needed (Pattern 3 above). Measure the actual cost with a realistic fixture. For a typical 30-question form, re-extraction is ~10-20ms -- negligible compared to the agent's reasoning time.

**Warning signs:** `write_answers` latency increases by >500ms for normal documents.

### Pitfall 3: Excel/PDF Resolution is Trivially Different

**What goes wrong:** Assuming all three formats resolve the same way. For Excel, the "xpath" IS the cell_id (S1-R2-C3) -- the id_to_xpath is an identity mapping. For PDF, the "xpath" is the F-ID. The resolution code needs to handle these differences.

**Why it happens:** The existing `_build_relaxed_payloads()` in `tool_errors.py` already handles Excel/PDF with relaxed field names (cell_id, field_id, value). The new resolution must work within this existing pattern.

**How to avoid:** For Excel and PDF, pair_id IS the xpath (the identity mapping). Resolution just needs to confirm the pair_id exists in the id_to_xpath dict. The existing relaxed path already defaults mode to `replace_content`. The resolver returns the same value for all three formats through `compact.id_to_xpath`.

**Warning signs:** Excel/PDF answers with pair_id-only fail unexpectedly.

### Pitfall 4: Response Format Change Breaks Agents

**What goes wrong:** Adding a `warnings` key to the write_answers response dict could break agents that expect exactly `{file_bytes_b64: ...}` or `{file_path: ...}`.

**Why it happens:** Agents may destructure the response strictly.

**How to avoid:** Only add the `warnings` key when warnings exist (non-empty list). When no warnings, the response is identical to the current format. Document the new key as optional in the tool docstring.

**Warning signs:** Agents error on unexpected keys in the response.

### Pitfall 5: pair_id Not Found in id_to_xpath

**What goes wrong:** Agent sends a pair_id that doesn't exist in the document's compact extraction (typo, stale ID from a different document, or ID from raw extraction).

**Why it happens:** pair_ids are assigned during extraction and can become stale if the document is modified between extract and write calls.

**How to avoid:** When resolution fails for a pair_id, raise a clear ValueError: "pair_id 'T99-R1-C1' not found in document. Re-extract with extract_structure_compact to get current IDs." This matches the existing pattern for xpath-not-found errors.

**Warning signs:** Silent writes to wrong locations, or cryptic KeyError exceptions.

## Code Examples

### Example 1: AnswerPayload Model Change

```python
# In models.py - make xpath and mode optional
class AnswerPayload(BaseModel):
    pair_id: str
    xpath: str | None = None                # Optional when answer_text provided
    insertion_xml: str | None = None
    answer_text: str | None = None
    mode: InsertionMode | None = None       # Defaults to replace_content
    confidence: Confidence = Confidence.KNOWN
```

### Example 2: Resolution in _build_word_payloads

```python
# In tool_errors.py - resolve xpaths for answer_text answers
def _build_word_payloads(
    answer_dicts: list[dict],
    file_bytes: bytes | None = None,
    file_type: FileType | None = None,
) -> tuple[list[AnswerPayload], list[str]]:
    """Word validation with optional pair_id resolution.

    Returns (payloads, warnings). Warnings are cross-check messages.
    """
    warnings: list[str] = []

    # Determine which answers need resolution
    needs_resolution = any(
        not a.get("xpath") and _is_provided(a.get("answer_text"))
        for a in answer_dicts
    )
    needs_cross_check = any(
        a.get("xpath") and a.get("pair_id")
        for a in answer_dicts
    )

    resolved: dict[str, str] = {}
    if (needs_resolution or needs_cross_check) and file_bytes:
        from src.pair_id_resolver import resolve_pair_ids
        pair_ids = [a["pair_id"] for a in answer_dicts if a.get("pair_id")]
        resolved = resolve_pair_ids(file_bytes, file_type, pair_ids)

    # ... build payloads, fill in missing xpaths from resolved ...
    # ... cross-check and add warnings ...

    return results, warnings
```

### Example 3: Response with Warnings

```python
# In tools_write.py - include warnings in response
response = {"file_bytes_b64": base64.b64encode(result_bytes).decode()}
if warnings:
    response["warnings"] = warnings
return response
```

### Example 4: Validation Split for answer_text vs insertion_xml

```python
# In tool_errors.py - different requirements for the two paths
for i, a in enumerate(answer_dicts):
    has_answer_text = _is_provided(a.get("answer_text"))
    has_insertion_xml = _is_provided(a.get("insertion_xml"))

    if has_insertion_xml:
        # Legacy path: xpath and mode REQUIRED
        if "xpath" not in a or "mode" not in a:
            errors.append(
                f"Answer '{pair_id}' (index {i}): insertion_xml requires "
                f"explicit xpath and mode."
            )
    elif has_answer_text:
        # Fast path: xpath optional (resolved from pair_id), mode defaults
        if not a.get("xpath") and not resolved.get(a.get("pair_id", "")):
            errors.append(
                f"Answer '{pair_id}' (index {i}): No xpath provided and "
                f"pair_id could not be resolved. Re-extract with "
                f"extract_structure_compact."
            )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Agent provides xpath, mode, insertion_xml for every answer | Agent can provide answer_text (server builds XML) | v2.0, Phase 6 | Eliminated build_insertion_xml round-trips |
| Agent must always provide xpath | (This phase) Server resolves xpath from pair_id | v2.1, Phase 8 | Eliminates agent xpath bookkeeping |
| Agent must always provide mode | (This phase) Server defaults mode to replace_content | v2.1, Phase 8 | Reduces answer payload to pair_id + answer_text |

**After this phase, minimal agent payload:**
```json
{
    "pair_id": "T1-R2-C2",
    "answer_text": "Acme Corporation"
}
```

(vs current minimum):
```json
{
    "pair_id": "T1-R2-C2",
    "xpath": "/w:body/w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]",
    "answer_text": "Acme Corporation",
    "mode": "replace_content"
}
```

## Open Questions

1. **Where should resolution logic live -- tool_errors.py or a new module?**
   - What we know: `tool_errors.py` handles all payload validation today (185 lines). Adding resolution logic (resolver + cross-check) would add ~60 lines.
   - What's unclear: Whether this pushes `tool_errors.py` past the 200-line limit.
   - Recommendation: Create `pair_id_resolver.py` (~50 lines) with `resolve_pair_ids()` and `cross_check_xpaths()`. Call from `tool_errors.py`. This keeps tool_errors focused on validation and the resolver testable in isolation.

2. **Should file_bytes be passed through build_answer_payloads?**
   - What we know: Currently `build_answer_payloads(answer_dicts, ft)` takes only the dicts and file type. Resolution needs file_bytes too.
   - What's unclear: Whether to change the function signature (adding file_bytes) or resolve at the tools_write.py level before calling build_answer_payloads.
   - Recommendation: Add `file_bytes` as an optional parameter to `build_answer_payloads()`. When None, resolution is skipped and xpath is required (backward compatible). This keeps the resolution close to the validation where it's needed.

3. **Should the response format change be additive-only?**
   - What we know: Current response is `{file_bytes_b64: ...}` or `{file_path: ...}`. Adding `warnings` is additive.
   - What's unclear: Whether to also add `resolved_from` metadata per answer (like Phase 10's verify_output plans).
   - Recommendation: Keep it minimal for Phase 8 -- just add `warnings: list[str]` when non-empty. Phase 10 can add per-answer metadata if needed.

4. **Do Excel/PDF need explicit resolution, or is the relaxed path already sufficient?**
   - What we know: `_build_relaxed_payloads()` already defaults mode and accepts cell_id/field_id as alternatives to xpath. Excel/PDF pair_ids (S1-R2-C3, F1) are the same as their xpaths (identity mapping in id_to_xpath).
   - What's unclear: Whether the relaxed path needs any changes at all for ERG-03/ERG-04.
   - Recommendation: The relaxed path already handles ERG-04 (mode defaults). For ERG-03, the relaxed path already accepts `pair_id` as the identifier and maps it to xpath. The only gap is cross-checking (ERG-05), which should work the same way -- re-extract, compare. But since Excel/PDF xpaths ARE the pair_ids, cross-checking is trivially a string equality check. Focus resolution changes on the Word path; verify Excel/PDF already satisfy ERG-03/ERG-04 through existing code.

## Sources

### Primary (HIGH confidence)

- **Codebase analysis**: Direct reading of all source files in `src/` and `tests/`. All findings verified against actual code.
  - `src/handlers/word_location_validator.py` -- existing id_to_xpath resolution pattern (lines 60-65)
  - `src/handlers/word_indexer.py` -- compact extraction producing id_to_xpath
  - `src/handlers/excel_indexer.py` -- identity mapping (id_to_xpath[element_id] = element_id)
  - `src/handlers/pdf_indexer.py` -- F-ID to native name mapping
  - `src/models.py` -- current AnswerPayload definition (xpath required, mode required)
  - `src/tool_errors.py` -- payload construction and validation (_build_word_payloads, _build_relaxed_payloads)
  - `src/tools_write.py` -- write_answers tool and response format
  - `src/handlers/word_writer.py` -- _apply_answer uses answer.xpath
  - `src/handlers/word_dry_run.py` -- preview_answers uses answer.xpath
- **Planning documents**: REQUIREMENTS.md (ERG-03/04/05), ROADMAP.md (Phase 8 success criteria), PROJECT.md (stateless constraint)

### Secondary (MEDIUM confidence)

- **Pydantic documentation** (from training data): Optional field handling with defaults. Pydantic v2 supports `field: Type | None = None` natively. This project already uses this pattern extensively (e.g., `insertion_xml: str | None = None` on AnswerPayload).

### Tertiary (LOW confidence)

None -- all findings are from direct codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing libraries
- Architecture: HIGH -- pattern directly mirrors existing word_location_validator.py
- Pitfalls: HIGH -- identified from direct code reading and understanding of existing validation flow

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable -- internal codebase, no external API changes expected)
