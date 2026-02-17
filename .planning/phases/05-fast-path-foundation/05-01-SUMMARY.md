---
phase: 05-fast-path-foundation
plan: 01
subsystem: api
tags: [pydantic, lxml, ooxml, formatting, models]

# Dependency graph
requires:
  - phase: 04-cross-platform-verification
    provides: "Stable AnswerPayload model and xml_formatting module"
provides:
  - "AnswerPayload with optional answer_text field for fast path"
  - "extract_formatting_from_element() public function for pre-parsed elements"
  - "Single code path for formatting extraction (delegation pattern)"
affects: [05-02, 06-fast-path-implementation]

# Tech tracking
tech-stack:
  added: []
  patterns: ["delegation pattern: extract_formatting delegates to extract_formatting_from_element"]

key-files:
  created: []
  modified:
    - src/models.py
    - src/xml_formatting.py
    - src/xml_utils.py
    - tests/test_xml_utils.py

key-decisions:
  - "Made insertion_xml optional (str | None = None) alongside new answer_text field for backward compatibility"
  - "extract_formatting_from_element placed before extract_formatting in source order as the primary extraction path"
  - "extract_formatting delegates to extract_formatting_from_element to ensure single code path"

patterns-established:
  - "Delegation pattern: string-based functions parse then delegate to element-based functions"

requirements-completed: [FAST-05, COMPAT-01]

# Metrics
duration: 2min
completed: 2026-02-17
---

# Phase 5 Plan 1: Fast Path Foundation Summary

**Optional answer_text field on AnswerPayload and public extract_formatting_from_element() for Phase 6 fast path**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-17T09:07:55Z
- **Completed:** 2026-02-17T09:10:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added optional `answer_text` field to `AnswerPayload` model for the fast path (Phase 6)
- Made `insertion_xml` optional with `None` default (backward compatible with all 234 existing tests)
- Created `extract_formatting_from_element()` as a public function accepting pre-parsed lxml elements
- Refactored `extract_formatting()` to delegate to the element-based function (single code path)
- Re-exported `extract_formatting_from_element` through `xml_utils.py` barrel module
- Added 4 parity tests confirming element-based and string-based paths produce identical results

## Task Commits

Each task was committed atomically:

1. **Task 1: Update AnswerPayload model and create extract_formatting_from_element** - `bff2322` (feat)
2. **Task 2: Add tests for extract_formatting_from_element parity** - `937d0aa` (test)

## Files Created/Modified
- `src/models.py` - Added optional `answer_text` field, made `insertion_xml` optional
- `src/xml_formatting.py` - Added `extract_formatting_from_element()`, refactored `extract_formatting()` to delegate
- `src/xml_utils.py` - Added `extract_formatting_from_element` to barrel re-exports
- `tests/test_xml_utils.py` - Added `TestExtractFormattingFromElement` class with 4 parity tests

## Decisions Made
- Made `insertion_xml` optional (`str | None = None`) alongside the new `answer_text` field. This is backward compatible because all existing callers provide `insertion_xml` explicitly. Phase 6 will add routing logic to use `answer_text` when `insertion_xml` is `None`.
- Placed `extract_formatting_from_element` before `extract_formatting` in source order since it is now the primary extraction path.
- Used delegation pattern: `extract_formatting()` parses string then calls `extract_formatting_from_element()`, ensuring a single code path for formatting extraction logic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `AnswerPayload` API contract is ready for Phase 6 fast path implementation
- `extract_formatting_from_element()` is available for Phase 6 to use with pre-parsed XPath elements
- All 238 tests pass (234 original + 4 new parity tests)
- Plan 05-02 can proceed (no blocking dependencies within this wave)

## Self-Check: PASSED

- All 4 modified/created files exist on disk
- Both task commits (bff2322, 937d0aa) found in git history

---
*Phase: 05-fast-path-foundation*
*Completed: 2026-02-17*
