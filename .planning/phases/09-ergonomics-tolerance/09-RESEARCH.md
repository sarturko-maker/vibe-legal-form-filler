# Phase 9: Ergonomics & Tolerance - Research

**Researched:** 2026-02-17
**Domain:** MCP tool API ergonomics, agent-friendly error messages, SKIP convention
**Confidence:** HIGH

## Summary

Phase 9 is a focused set of four small, self-contained improvements to the existing MCP tool API. No new libraries are needed. No architectural changes. Every requirement maps to a specific, well-understood code location with clear before/after behavior. The changes are additive and backward-compatible.

The four requirements break into two categories: (1) **ergonomics** (ERG-01, ERG-02) -- reducing cognitive overhead for agents by echoing file_path in responses and improving error messages, and (2) **tolerance** (TOL-01, TOL-02) -- letting agents explicitly skip fields via `answer_text="SKIP"` without the server treating it as a missing field or writing "SKIP" into the document.

**Primary recommendation:** Implement as a single plan with four small tasks, one per requirement. Each task is a localized change to 1-2 source files plus corresponding tests. No refactoring needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ERG-01 | `extract_structure_compact` response includes `file_path` when provided as input | Add optional `file_path` field to `CompactStructureResponse` model; set it in `tools_extract.py` when `file_path` argument is non-empty |
| ERG-02 | `write_answers` error for missing file input says "Missing file_path -- this is the path you passed to extract_structure_compact" | Change the error message in `validators.py:resolve_file_input()` or in `tool_errors.py:resolve_file_for_tool()` for the `write_answers` tool name |
| TOL-01 | `answer_text="SKIP"` recognized as intentional skip -- no write, status="skipped" in response | Intercept SKIP answers in `tool_errors.py` or `tools_write.py` before they reach the handler; filter them out of the payloads list; return per-answer status in response |
| TOL-02 | Skipped fields reported in `write_answers` response summary with count | Add summary dict to `write_answers` response with written/skipped counts |
</phase_requirements>

## Standard Stack

### Core

No new libraries. This phase uses only what is already installed:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | (existing) | Model schema for CompactStructureResponse | Already used for all models |
| pytest | (existing) | Tests for all four requirements | Already the test framework |

### Supporting

None needed.

### Alternatives Considered

None -- these are pure internal code changes with no library choices to make.

## Architecture Patterns

### Pattern 1: Optional Field on Pydantic Response Model (ERG-01)

**What:** Add an optional `file_path: str | None = None` field to `CompactStructureResponse` in `models.py`. When `model_dump()` is called, the field appears in the JSON response if set. When not set, it serializes as `null` (or can be excluded with `model_dump(exclude_none=True)` -- but the existing pattern includes all fields, which is fine).

**When to use:** When the response needs to echo back an input parameter for agent convenience.

**Exact change locations:**

1. `src/models.py` line 60-69 -- add `file_path: str | None = None` to `CompactStructureResponse`
2. `src/tools_extract.py` line 50-82 -- set `file_path` on the response dict after `model_dump()`, OR better: pass `file_path` to the indexer and let it populate the model

**Recommended approach:** The cleanest path is to add the field to the model and set it at the tool level in `tools_extract.py` after the `model_dump()` call. This avoids changing the three indexer functions (word/excel/pdf) which are internal and do not receive the file_path. The tool function in `tools_extract.py` already has access to the `file_path` argument.

```python
# In tools_extract.py, extract_structure_compact():
result = word_extract_compact(raw).model_dump()
if file_path:
    result["file_path"] = file_path
return result
```

This approach is simpler than modifying the Pydantic model because:
- The indexers (word/excel/pdf) do not need to know about file_path
- The field is set only at the tool layer where the input is available
- It avoids passing file_path through the internal extraction pipeline

**Alternative:** Add `file_path` to the `CompactStructureResponse` model. This is slightly more formal but forces the indexers to either accept file_path or the tool layer to construct the response differently. The dict-injection approach above is simpler and matches the existing pattern where `model_dump()` returns a dict that can be augmented before returning.

### Pattern 2: Tool-Specific Error Messages (ERG-02)

**What:** The existing `resolve_file_for_tool()` wrapper in `tool_errors.py` already receives the `tool_name` parameter. It wraps the generic error from `validators.py` with tool-specific context. The current error for "neither file_path nor file_bytes_b64 provided" is:

```
Provide either file_path or file_bytes_b64. Neither was supplied.
```

The requirement wants the `write_answers` tool to say:

```
Missing file_path -- this is the path you passed to extract_structure_compact
```

**Exact change location:** `src/tool_errors.py`, `resolve_file_for_tool()` function (lines 110-124). The function already catches ValueError from `resolve_file_input()` and re-raises with tool context. We can check if `tool_name == "write_answers"` and if the error matches "Neither was supplied", then replace the message.

```python
def resolve_file_for_tool(tool_name, file_bytes_b64, file_type, file_path):
    try:
        return resolve_file_input(file_bytes_b64, file_type, file_path)
    except ValueError as exc:
        msg = str(exc)
        if tool_name == "write_answers" and "Neither was supplied" in msg:
            raise ValueError(
                "Missing file_path -- this is the path you passed to "
                "extract_structure_compact"
            ) from exc
        example = USAGE.get(tool_name, tool_name)
        raise ValueError(f"{tool_name} error: {msg}\n  Example: {example}") from exc
```

### Pattern 3: SKIP Sentinel Detection (TOL-01)

**What:** When `answer_text="SKIP"` (case-insensitive), the server should:
1. NOT write anything to the document for that field
2. Return `status="skipped"` for that answer in the response
3. NOT treat "SKIP" as "neither answer_text nor insertion_xml provided" (i.e., it should pass validation)

**Key insight:** The `_is_provided()` function currently returns `True` for `"SKIP"` because it is non-empty. So validation will pass. The question is WHERE to intercept and filter.

**Two approaches:**

**Approach A (recommended): Filter at the tools_write.py level**
- After `build_answer_payloads()` returns the payloads list, partition into skip/write lists
- Pass only non-skip payloads to the handler
- Collect skip statuses and include them in the response

```python
# In tools_write.py, write_answers():
payloads, warnings = build_answer_payloads(answer_dicts, ft, raw)
skip_payloads = [p for p in payloads if _is_skip(p)]
write_payloads = [p for p in payloads if not _is_skip(p)]
# ... write only write_payloads ...
# ... include skip info in response ...
```

**Approach B: Filter at the tool_errors.py level**
- Detect SKIP during payload construction and either exclude from the payloads list or mark them specially
- This is more complex because `build_answer_payloads` would need to return a third value (skip list)

**Recommended: Approach A.** Filtering at the `tools_write.py` level keeps the separation of concerns clean: `tool_errors.py` handles validation, `tools_write.py` handles routing. The SKIP detection is a one-liner: `answer.answer_text and answer.answer_text.strip().upper() == "SKIP"`.

**Case sensitivity:** The requirement says `answer_text="SKIP"`. Should "skip", "Skip", "SKIP" all work? The safest choice is case-insensitive matching (`.upper() == "SKIP"`) to be tolerance-friendly. This matches how the checkbox coercion works in pdf_writer.py (case-insensitive "true"/"yes"/"1").

### Pattern 4: Response Summary with Counts (TOL-02)

**What:** The `write_answers` response currently returns either `{file_bytes_b64: ...}` or `{file_path: ...}`, optionally with `warnings`. The requirement adds a `summary` dict with written/skipped counts.

**Current response shape:**
```json
{"file_path": "/path/to/filled.docx", "warnings": ["..."]}
```

**Required response shape:**
```json
{
  "file_path": "/path/to/filled.docx",
  "warnings": ["..."],
  "summary": {"written": 42, "skipped": 3}
}
```

**Exact change location:** `src/tools_write.py`, the `write_answers()` function (lines 118-153). After writing, add the summary to the response dict.

**Important consideration:** The summary should always be present (not just when there are skips). This way agents can always parse it consistently. When there are no skips, the count is 0.

### Anti-Patterns to Avoid

- **Modifying handler-level code for SKIP logic:** The handlers (word_writer, excel_writer, pdf_writer) should never see SKIP answers. Filtering happens at the tool level before dispatching to handlers.
- **Adding file_path to indexer function signatures:** The indexers extract document structure from bytes. They should not be aware of filesystem paths. The file_path echo is a tool-level concern.
- **Breaking backward compatibility on response shape:** All new fields (`file_path`, `summary`) must be additive. Existing agents that do not check for these fields must not break.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| N/A | N/A | N/A | All changes are simple additions to existing code |

**Key insight:** This phase has no "don't hand-roll" concerns. Every requirement is a small, localized change. No complex algorithms, no parsing, no format conversion.

## Common Pitfalls

### Pitfall 1: SKIP Bypassing Validation

**What goes wrong:** If SKIP detection happens before `_validate_answer_text_xml_fields()`, a SKIP answer might bypass the exactly-one-of check. But since `_is_provided("SKIP")` returns `True`, this is actually fine -- SKIP passes validation as a valid `answer_text` value. The filtering happens AFTER validation.

**Why it happens:** Confusion about validation order.

**How to avoid:** Filter SKIP answers AFTER `build_answer_payloads()` returns validated payloads. The SKIP answer passes all validation as a normal answer_text, then gets filtered at the routing layer.

**Warning signs:** Tests where SKIP answers are rejected by validation.

### Pitfall 2: SKIP Case Sensitivity

**What goes wrong:** An agent sends `answer_text="skip"` (lowercase) and the server writes "skip" as the answer text instead of skipping.

**Why it happens:** Exact string match instead of case-insensitive.

**How to avoid:** Use `.strip().upper() == "SKIP"` for detection. Document the convention as case-insensitive.

**Warning signs:** Tests only check uppercase SKIP.

### Pitfall 3: Empty Payloads After Filtering

**What goes wrong:** If ALL answers are SKIP, the write_payloads list is empty. Passing an empty list to the handler might cause unexpected behavior or an empty document.

**Why it happens:** Edge case not considered.

**How to avoid:** If all payloads are skipped, return the original file bytes unchanged (or skip the write call entirely). The summary should show `{"written": 0, "skipped": N}`.

**Warning signs:** No test for "all answers are SKIP" case.

### Pitfall 4: file_path Echo for Base64 Input

**What goes wrong:** When the agent provides `file_bytes_b64` instead of `file_path`, the response should NOT include `file_path` (or it should be `null`). Including a meaningless value would confuse agents.

**Why it happens:** Unconditionally setting `file_path` in the response.

**How to avoid:** Only set `file_path` in the response when the input `file_path` argument is non-empty. The `or None` pattern works: `file_path or None`.

**Warning signs:** Response includes `file_path: ""` when base64 input was used.

### Pitfall 5: dry_run Interaction with SKIP

**What goes wrong:** When `dry_run=True`, SKIP answers should still appear in the preview but with `status="skipped"` instead of being silently dropped.

**Why it happens:** SKIP filtering applied before dry_run branching.

**How to avoid:** In dry_run mode, include SKIP answers in the preview with a clear status. The filtering-before-write should happen only on the actual write path.

**Warning signs:** dry_run response omits SKIP answers entirely.

### Pitfall 6: ERG-02 Error Message Specificity

**What goes wrong:** The improved error message for `write_answers` might accidentally apply to other tools that also call `resolve_file_for_tool`.

**Why it happens:** Overly broad pattern matching in the error handler.

**How to avoid:** Check `tool_name == "write_answers"` explicitly before overriding the error message.

**Warning signs:** `extract_structure_compact` shows "this is the path you passed to extract_structure_compact" error (wrong context).

## Code Examples

### ERG-01: file_path Echo in extract_structure_compact Response

```python
# In src/tools_extract.py, extract_structure_compact():
@mcp.tool()
def extract_structure_compact(
    file_bytes_b64: str = "",
    file_type: str = "",
    file_path: str = "",
) -> dict:
    raw, ft = resolve_file_for_tool(
        "extract_structure_compact",
        file_bytes_b64 or None, file_type or None, file_path or None,
    )

    if ft == FileType.WORD:
        result = word_extract_compact(raw).model_dump()
    elif ft == FileType.EXCEL:
        result = excel_extract_compact(raw).model_dump()
    elif ft == FileType.PDF:
        result = pdf_extract_compact(raw).model_dump()
    else:
        raise NotImplementedError(...)

    if file_path:
        result["file_path"] = file_path
    return result
```

### ERG-02: Improved Error Message for write_answers

```python
# In src/tool_errors.py, resolve_file_for_tool():
def resolve_file_for_tool(tool_name, file_bytes_b64, file_type, file_path):
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
            f"{tool_name} error: {msg}\n  Example: {example}"
        ) from exc
```

### TOL-01/TOL-02: SKIP Detection and Summary

```python
# In src/tools_write.py

def _is_skip(payload: AnswerPayload) -> bool:
    """Return True if the answer is an intentional SKIP."""
    return (
        payload.answer_text is not None
        and payload.answer_text.strip().upper() == "SKIP"
    )

# In write_answers(), after build_answer_payloads:
payloads, warnings = build_answer_payloads(answer_dicts, ft, raw)
skipped = [p for p in payloads if _is_skip(p)]
to_write = [p for p in payloads if not _is_skip(p)]

# ... write to_write as before ...

summary = {
    "written": len(to_write),
    "skipped": len(skipped),
}
if skipped:
    summary["skipped_pairs"] = [s.pair_id for s in skipped]

response["summary"] = summary
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Agent must track file_path separately | Server echoes file_path in extract response | Phase 9 | Fewer agent state variables |
| Generic "provide file_path or b64" error | Contextual error pointing to extract_structure_compact | Phase 9 | Agent self-corrects in one retry |
| No skip convention; agent omits or writes empty | Explicit SKIP sentinel with status reporting | Phase 9 | Clear contract for intentionally blank fields |

## Open Questions

1. **Should `summary` always be present or only when skips exist?**
   - What we know: Success criterion 4 says "42 written, 3 skipped" format
   - What's unclear: Whether to include summary when there are 0 skips
   - Recommendation: Always include summary for consistency. `{"written": 45, "skipped": 0}` is clearer than conditionally omitting it.

2. **Should dry_run preview show SKIP answers?**
   - What we know: dry_run returns preview array; SKIP answers should not result in writes
   - What's unclear: Should the preview include SKIP answers with a "skipped" status, or omit them?
   - Recommendation: Include them with `status="skipped"` so the agent sees the full picture. This is consistent with the dry_run purpose of previewing what will happen.

3. **Success criterion 5 (mode defaults) -- already implemented?**
   - What we know: Phase 8 Plan 2 already implemented mode defaulting to `replace_content` when `answer_text` is provided and mode is omitted (in `_build_word_payloads`, line 283 of `tool_errors.py`)
   - What's unclear: Whether this is considered "done" or needs re-verification
   - Recommendation: This is already implemented. Phase 9 should include a verification test but does not need new implementation code. The success criterion should be confirmed by the existing test `test_write_answers_pair_id_only_defaults_mode` in `tests/test_resolution.py`.

## Codebase Analysis

### Files That Must Change

| File | Change | Requirement |
|------|--------|-------------|
| `src/tools_extract.py` | Add file_path to response dict | ERG-01 |
| `src/tool_errors.py` | Customize write_answers error message | ERG-02 |
| `src/tools_write.py` | SKIP detection, filtering, summary in response | TOL-01, TOL-02 |

### Files That Might Change

| File | Change | Condition |
|------|--------|-----------|
| `src/models.py` | Add file_path to CompactStructureResponse | Only if we want Pydantic validation; dict injection is simpler |

### Files That Must NOT Change

| File | Reason |
|------|--------|
| `src/handlers/word_indexer.py` | Indexers should not know about file_path |
| `src/handlers/excel_indexer.py` | Same |
| `src/handlers/pdf_indexer.py` | Same |
| `src/handlers/word_writer.py` | Handlers should not see SKIP answers |
| `src/handlers/excel_writer.py` | Same |
| `src/handlers/pdf_writer.py` | Same |
| `src/validators.py` | Generic validation stays generic; tool-specific messages go in tool_errors.py |

### Existing Test Count

295 tests across 22 test files. All must continue passing after changes.

### Estimated New Tests

| Requirement | Tests | Description |
|-------------|-------|-------------|
| ERG-01 | 2-3 | file_path echoed when provided; not echoed when b64 used; echoed for all file types |
| ERG-02 | 1-2 | write_answers error mentions extract_structure_compact; other tools still show generic error |
| TOL-01 | 3-4 | SKIP detected case-insensitively; SKIP answers not written; non-SKIP answers still written; all-SKIP returns unchanged bytes |
| TOL-02 | 2 | Summary counts in response; summary present even with 0 skips |
| **Total** | ~10 | |

## Sources

### Primary (HIGH confidence)

- Codebase inspection: `src/tools_extract.py`, `src/tools_write.py`, `src/tool_errors.py`, `src/models.py`, `src/validators.py` -- all change locations verified by reading current code
- Codebase inspection: `src/handlers/{word,excel,pdf}_indexer.py` -- confirmed indexers return `CompactStructureResponse` via `model_dump()`
- Codebase inspection: `src/pair_id_resolver.py`, `src/handlers/{word,excel,pdf}.py` -- confirmed handler dispatch pattern
- Phase 8 summaries: `08-01-SUMMARY.md`, `08-02-SUMMARY.md` -- confirmed mode defaulting already implemented
- Requirements: `.planning/REQUIREMENTS.md` -- ERG-01, ERG-02, TOL-01, TOL-02 definitions

### Secondary (MEDIUM confidence)

- None needed. All findings are from direct codebase inspection.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, pure code changes
- Architecture: HIGH -- all patterns verified against existing codebase
- Pitfalls: HIGH -- enumerated from direct code analysis of validation/dispatch flow

**Research date:** 2026-02-17
**Valid until:** indefinite (codebase-specific findings, not library-version-dependent)
