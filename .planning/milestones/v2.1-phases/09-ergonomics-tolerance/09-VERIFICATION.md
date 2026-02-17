---
phase: 09-ergonomics-tolerance
verified: 2026-02-17T19:45:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 9: Ergonomics & Tolerance Verification Report

**Phase Goal:** Small API improvements that reduce agent friction — file_path echo, better errors, SKIP convention, mode defaults
**Verified:** 2026-02-17T19:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | extract_structure_compact response includes file_path when agent provides file_path input | ✓ VERIFIED | tools_extract.py lines 84-86 inject file_path into result dict; test passes |
| 2 | extract_structure_compact response does NOT include file_path when agent uses file_bytes_b64 | ✓ VERIFIED | tools_extract.py line 84 checks `if file_path:` before injection; test passes |
| 3 | write_answers error for missing file mentions extract_structure_compact by name | ✓ VERIFIED | tool_errors.py lines 121-125 check tool_name and message pattern; test passes |
| 4 | answer_text='SKIP' (case-insensitive) causes no write and status='skipped' in response | ✓ VERIFIED | tools_write.py lines 48-57 define _is_skip; lines 139-140 partition payloads; dry_run includes skipped entries; tests pass |
| 5 | write_answers response always includes a summary dict with written and skipped counts | ✓ VERIFIED | tools_write.py line 171 builds summary; lines 180, 186 attach to response; tests pass |
| 6 | All-SKIP edge case returns original file bytes unchanged | ✓ VERIFIED | tools_write.py lines 157-169 check `if to_write:` else return raw bytes; test passes |
| 7 | dry_run shows SKIP answers with status='skipped' | ✓ VERIFIED | tools_write.py lines 142-155 append skipped entries to preview; test passes |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/tools_extract.py` | file_path echo in extract_structure_compact response | ✓ VERIFIED | Lines 84-86: `if file_path: result["file_path"] = file_path`. Pattern found. Wired: imported by mcp_app, registered as MCP tool. |
| `src/tool_errors.py` | write_answers-specific error message | ✓ VERIFIED | Lines 121-125: Special case for write_answers with "Missing file_path" message mentioning extract_structure_compact. Pattern found. Wired: called by resolve_file_for_tool, used in tools_write.py. |
| `src/tools_write.py` | SKIP detection, filtering, summary in response | ✓ VERIFIED | Lines 48-57: `_is_skip()` helper. Lines 139-140: partition payloads. Line 171: summary dict. Lines 144-155: dry_run skipped entries. All patterns found. Wired: imported by mcp_app, registered as MCP tool. |
| `tests/test_ergonomics.py` | Tests for all four requirements | ✓ VERIFIED | 213 lines, 11 test methods covering ERG-01, ERG-02, TOL-01, TOL-02. All tests pass. Min line requirement (80) exceeded. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/tools_extract.py` | extract_structure_compact response dict | dict injection after model_dump() | ✓ WIRED | Line 85: `result["file_path"] = file_path` after model_dump() at lines 74-78. Conditional on file_path being provided. |
| `src/tool_errors.py` | validators.py resolve_file_input | catch ValueError, check tool_name | ✓ WIRED | Lines 117-130: resolve_file_for_tool calls resolve_file_input (line 118), catches ValueError (line 119), checks tool_name == "write_answers" (line 121). |
| `src/tools_write.py` | _is_skip and payload filtering | SKIP filtering after build_answer_payloads | ✓ WIRED | Lines 137-140: build_answer_payloads returns payloads, then partitioned into skipped/to_write using _is_skip. Lines 142-155: dry_run uses partition. Lines 157-169: write path uses to_write. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ERG-01 | 09-01-PLAN.md | extract_structure_compact response includes file_path when provided as input | ✓ SATISFIED | tools_extract.py lines 84-86. Test: test_extract_compact_echoes_file_path. Runtime verification confirms file_path echo and no echo for b64. |
| ERG-02 | 09-01-PLAN.md | write_answers error for missing file says "Missing file_path -- this is the path you passed to extract_structure_compact" | ✓ SATISFIED | tool_errors.py lines 121-125. Test: test_write_answers_missing_file_error_mentions_extract. Runtime verification confirms error message content. |
| TOL-01 | 09-01-PLAN.md | answer_text="SKIP" recognized as intentional skip (no write, status="skipped" in response) | ✓ SATISFIED | tools_write.py lines 48-57, 139-140, 144-149. Tests: test_skip_answer_not_written, test_skip_case_insensitive, test_all_skip_returns_original. Runtime verification confirms SKIP detection and filtering. |
| TOL-02 | 09-01-PLAN.md | Skipped fields reported in write_answers response summary with count | ✓ SATISFIED | tools_write.py line 171, 180, 186. Tests: test_summary_always_present, test_summary_with_skips, test_dry_run_shows_skip_status. Runtime verification confirms summary presence and counts. |

**Coverage:** 4/4 requirements satisfied (ERG-01, ERG-02, TOL-01, TOL-02)

**No orphaned requirements:** REQUIREMENTS.md maps ERG-01, ERG-02, TOL-01, TOL-02 to Phase 9. All appear in 09-01-PLAN.md frontmatter. No additional requirements mapped to Phase 9.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No anti-patterns detected |

**Scanned files:**
- `src/tools_extract.py` — No TODO/FIXME/placeholder comments, no empty implementations
- `src/tool_errors.py` — No TODO/FIXME/placeholder comments, no empty implementations
- `src/tools_write.py` — No TODO/FIXME/placeholder comments, no empty implementations
- `tests/test_ergonomics.py` — Substantive tests with real assertions

### Human Verification Required

None. All verifications are deterministic and automated via tests.

---

## Detailed Verification Evidence

### Truth 1: file_path echo when provided

**Code evidence:**
```python
# src/tools_extract.py lines 84-86
if file_path:
    result["file_path"] = file_path
return result
```

**Test evidence:**
- `test_extract_compact_echoes_file_path` — passes
- `test_extract_compact_echoes_file_path_excel` — passes

**Runtime verification:**
```python
result1 = extract_structure_compact(file_path='tests/fixtures/table_questionnaire.docx')
assert 'file_path' in result1
assert result1['file_path'] == 'tests/fixtures/table_questionnaire.docx'
# ✓ PASS
```

### Truth 2: no file_path echo for b64

**Code evidence:** Same `if file_path:` check means no injection when file_path is empty/None

**Test evidence:**
- `test_extract_compact_no_file_path_for_b64` — passes

**Runtime verification:**
```python
result2 = extract_structure_compact(file_bytes_b64=b64, file_type='word')
assert 'file_path' not in result2
# ✓ PASS
```

### Truth 3: write_answers error mentions extract_structure_compact

**Code evidence:**
```python
# src/tool_errors.py lines 121-125
if tool_name == "write_answers" and "Neither was supplied" in msg:
    raise ValueError(
        "Missing file_path -- this is the path you passed "
        "to extract_structure_compact"
    ) from exc
```

**Test evidence:**
- `test_write_answers_missing_file_error_mentions_extract` — passes
- `test_other_tool_error_does_not_mention_extract` — passes (confirms specificity)

**Runtime verification:**
```python
try:
    write_answers(answers=[{'pair_id': 'T1-R2-C2', 'answer_text': 'X'}])
except ValueError as e:
    assert 'Missing file_path' in str(e)
    assert 'extract_structure_compact' in str(e)
# ✓ PASS
```

### Truth 4: SKIP detection (case-insensitive)

**Code evidence:**
```python
# src/tools_write.py lines 48-57
def _is_skip(payload) -> bool:
    return (
        payload.answer_text is not None
        and payload.answer_text.strip().upper() == "SKIP"
    )

# lines 139-140
skipped = [p for p in payloads if _is_skip(p)]
to_write = [p for p in payloads if not _is_skip(p)]
```

**Test evidence:**
- `test_skip_answer_not_written` — passes (SKIP cell remains empty)
- `test_skip_case_insensitive` — passes (lowercase "skip" recognized)

**Runtime verification:**
```python
result = write_answers(
    file_path=docx_path,
    answers=[
        {'pair_id': 'T1-R2-C2', 'answer_text': 'Acme Corp'},
        {'pair_id': 'T1-R3-C2', 'answer_text': 'SKIP'},
        {'pair_id': 'T1-R4-C2', 'answer_text': 'skip'},
    ],
    dry_run=True
)
assert result['summary']['written'] == 1
assert result['summary']['skipped'] == 2
# ✓ PASS
```

### Truth 5: summary always present

**Code evidence:**
```python
# src/tools_write.py line 171
summary = {"written": len(to_write), "skipped": len(skipped)}

# lines 180, 186
response["summary"] = summary  # both file_path and b64 branches
```

**Test evidence:**
- `test_summary_always_present` — passes (no SKIP answers)
- `test_summary_with_skips` — passes (mixed SKIP and non-SKIP)

**Runtime verification:**
```python
result = write_answers(...)
assert 'summary' in result
assert 'written' in result['summary']
assert 'skipped' in result['summary']
# ✓ PASS
```

### Truth 6: all-SKIP returns original bytes

**Code evidence:**
```python
# src/tools_write.py lines 157-169
if to_write:
    if ft == FileType.WORD:
        result_bytes = word_handler.write_answers(raw, to_write)
    # ...
else:
    result_bytes = raw  # All answers skipped, return original
```

**Test evidence:**
- `test_all_skip_returns_original` — passes (bytes comparison)

**Runtime verification:**
```python
original_bytes = Path(docx_path).read_bytes()
result = write_answers(
    answers=[
        {'pair_id': 'T1-R2-C2', 'answer_text': 'SKIP'},
        {'pair_id': 'T1-R3-C2', 'answer_text': 'SKIP'},
    ],
    file_path=docx_path,
)
returned_bytes = base64.b64decode(result['file_bytes_b64'])
assert returned_bytes == original_bytes
# ✓ PASS
```

### Truth 7: dry_run shows SKIP with status='skipped'

**Code evidence:**
```python
# src/tools_write.py lines 144-155
for p in skipped:
    result["preview"].append({
        "pair_id": p.pair_id,
        "xpath": p.xpath,
        "status": "skipped",
        "message": "Intentional SKIP -- field will not be written",
    })
result["summary"] = {
    "written": len(to_write),
    "skipped": len(skipped),
}
```

**Test evidence:**
- `test_dry_run_shows_skip_status` — passes (finds skipped entry in preview)

**Runtime verification:**
```python
result = write_answers(
    answers=[
        {'pair_id': 'T1-R2-C2', 'answer_text': 'Acme Corp'},
        {'pair_id': 'T1-R3-C2', 'answer_text': 'SKIP'},
    ],
    file_path=docx_path,
    dry_run=True,
)
skip_entries = [p for p in result['preview'] if p.get('status') == 'skipped']
assert len(skip_entries) == 1
assert skip_entries[0]['pair_id'] == 'T1-R3-C2'
# ✓ PASS
```

### Success Criterion 5: mode defaults

**Code evidence:**
```python
# src/tool_errors.py lines 288-302
mode_raw = a.get("mode")
if mode_raw is None and has_answer_text:
    mode = InsertionMode.REPLACE_CONTENT
elif mode_raw is not None:
    try:
        mode = InsertionMode(mode_raw)
    # ...
else:
    mode = InsertionMode.REPLACE_CONTENT
```

**Test evidence:**
- `test_write_answers_pair_id_only_defaults_mode` (from Phase 8) — passes

**Runtime verification:**
```python
result = write_answers(
    file_path=docx_path,
    answers=[
        {'pair_id': 'T1-R2-C2', 'answer_text': 'Acme Corp'}  # no mode field
    ],
    dry_run=True
)
# No error raised, mode was defaulted to replace_content
# ✓ PASS
```

---

## Test Results

**Total tests:** 306 (all passing)
**New tests (Phase 9):** 11 (all passing)
**Test file:** tests/test_ergonomics.py

**Test breakdown:**
1. ERG-01 tests: 3 (file_path echo for Word, no echo for b64, file_path echo for Excel)
2. ERG-02 tests: 2 (write_answers error mentions extract, other tools don't)
3. TOL-01 tests: 3 (SKIP not written, case-insensitive, all-SKIP returns original)
4. TOL-02 tests: 3 (summary always present, summary with skips, dry_run shows skip status)

**No regressions:** All 295 pre-existing tests still pass.

---

## Commits

Task commits found in git log:
1. `133ea98` — feat(09-01): add file_path echo and write_answers error message
2. `13db416` — feat(09-01): implement SKIP convention and response summary

Both commits exist and contain the expected changes.

---

## Summary

**All must-haves verified.** Phase goal achieved.

The API is now more self-describing and forgiving:
- Agents no longer need to track file_path separately
- Agents get clear, actionable error messages when they forget file_path
- Agents can signal intentionally blank fields with "SKIP"
- Agents always receive summary counts to track progress

All implementations are substantive (not stubs), wired (used in production code paths), and tested (11 new tests, all passing).

No anti-patterns detected. No human verification required. Ready to proceed to Phase 10 or 11.

---

_Verified: 2026-02-17T19:45:00Z_
_Verifier: Claude (gsd-verifier)_
