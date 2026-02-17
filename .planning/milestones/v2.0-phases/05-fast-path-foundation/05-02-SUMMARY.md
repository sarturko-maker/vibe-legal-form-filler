---
phase: 05-fast-path-foundation
plan: 02
subsystem: api
tags: [validation, pydantic, error-handling, batch-validation]

# Dependency graph
requires:
  - phase: 05-fast-path-foundation
    plan: 01
    provides: "AnswerPayload with optional answer_text and insertion_xml fields"
provides:
  - "Batch validation with exactly-one-of semantics for answer_text/insertion_xml"
  - "_is_provided() helper for None/empty/whitespace checking"
  - "Error aggregation listing all invalid answers in a single ValueError"
  - "answer_text accepted as alias on Excel/PDF relaxed path"
affects: [06-fast-path-implementation]

# Tech tracking
tech-stack:
  added: []
  patterns: ["batch validation with error aggregation (no short-circuiting)"]

key-files:
  created: []
  modified:
    - src/tool_errors.py
    - tests/test_e2e_integration.py

key-decisions:
  - "Empty strings and whitespace-only strings treated as 'not provided' per user decision"
  - "Batch validation collects ALL errors before raising, not short-circuiting on first"
  - "Entire batch rejected if ANY answer is invalid (no partial writes)"
  - "answer_text accepted as alias for value on the relaxed Excel/PDF path"

patterns-established:
  - "Batch validation pattern: iterate all, collect errors, raise once with count header"

requirements-completed: [FAST-04, COMPAT-01, COMPAT-02]

# Metrics
duration: 2min
completed: 2026-02-17
---

# Phase 5 Plan 2: Batch Validation for answer_text/insertion_xml Summary

**Exactly-one-of batch validation with error aggregation for answer_text/insertion_xml fields, rejecting both-provided and neither-provided with agent-friendly error messages**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-17T09:12:19Z
- **Completed:** 2026-02-17T09:15:17Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `_is_provided()` helper as single source of truth for field presence checking (None, empty, whitespace-only all treated as absent)
- Added `_validate_answer_text_xml_fields()` batch validator that collects ALL errors across a batch before raising
- Updated both Word and relaxed (Excel/PDF) payload builders to enforce exactly-one-of semantics
- Added 12 comprehensive integration tests covering all validation paths, error formats, and backward compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement batch validation logic in tool_errors.py** - `ca44327` (feat)
2. **Task 2: Add integration tests for answer_text/insertion_xml validation** - `3a72a52` (test)

## Files Created/Modified
- `src/tool_errors.py` - Added _is_provided, _validate_answer_text_xml_fields, updated _WORD_REQUIRED, _ALL_KNOWN_FIELDS, both payload builders, USAGE example
- `tests/test_e2e_integration.py` - Added TestAnswerTextValidation class with 12 tests

## Decisions Made
- Empty strings and whitespace-only strings are treated as "not provided" -- consistent with user decision in CONTEXT.md. The `_is_provided()` helper encapsulates this rule.
- Batch validation iterates ALL answers before raising, so agents see every error at once and can fix all in a single retry.
- Entire batch is rejected if any answer is invalid -- prevents partial document corruption from a half-written batch.
- On the relaxed Excel/PDF path, `answer_text` is accepted as an alias that falls through to `insertion_xml` (since Excel/PDF don't need real OOXML).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Validation layer complete: agents get clear, actionable errors for any misuse of answer_text/insertion_xml
- 250 tests pass (238 original + 12 new validation tests)
- Phase 5 complete: both plans (API contract + batch validation) are done
- Phase 6 (fast path implementation) can proceed with the routing logic

## Self-Check: PASSED

- src/tool_errors.py exists on disk
- tests/test_e2e_integration.py exists on disk
- Commit ca44327 found in git history
- Commit 3a72a52 found in git history

---
*Phase: 05-fast-path-foundation*
*Completed: 2026-02-17*
