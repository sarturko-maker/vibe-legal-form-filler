---
phase: 08-resolution-infrastructure
plan: 01
subsystem: api
tags: [pydantic, resolution, pair-id, xpath, cross-check]

# Dependency graph
requires:
  - phase: 05-fast-path-foundation
    provides: "AnswerPayload with answer_text field"
provides:
  - "pair_id_resolver module with resolve_pair_ids() and cross_check_xpaths()"
  - "AnswerPayload with optional xpath and mode fields"
affects: [08-02, tool_errors, tools_write]

# Tech tracking
tech-stack:
  added: []
  patterns: ["lazy imports in resolver to avoid circular deps", "re-extraction pattern for stateless resolution"]

key-files:
  created: ["src/pair_id_resolver.py", "tests/test_pair_id_resolver.py"]
  modified: ["src/models.py"]

key-decisions:
  - "Lazy imports inside resolve_pair_ids to avoid loading all three handlers at module level"
  - "Resolver returns dict omitting missing pair_ids rather than raising errors"

patterns-established:
  - "Stateless resolution: re-extract compact structure per call, no caching"
  - "Cross-check as advisory warnings, not blocking errors"

requirements-completed: [ERG-03, ERG-04, ERG-05]

# Metrics
duration: 2min
completed: 2026-02-17
---

# Phase 8 Plan 1: Resolution Infrastructure Summary

**pair_id_resolver module with resolve/cross-check functions and optional xpath/mode on AnswerPayload**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-17T14:00:09Z
- **Completed:** 2026-02-17T14:02:55Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created pair_id_resolver.py with resolve_pair_ids() supporting Word, Excel, and PDF file types via lazy imports
- Created cross_check_xpaths() that warns when agent-provided xpath differs from resolved xpath
- Made xpath and mode optional on AnswerPayload (str | None = None, InsertionMode | None = None)
- 8 new tests covering resolution for all three file types and all cross-check scenarios
- All 289 tests pass (281 existing + 8 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pair_id_resolver.py with resolve and cross-check functions** - `5b7e120` (feat)
2. **Task 2: Make xpath and mode optional on AnswerPayload** - `da2e18f` (feat)

## Files Created/Modified
- `src/pair_id_resolver.py` - Resolves pair_ids to xpaths via compact re-extraction; cross-checks agent xpaths
- `tests/test_pair_id_resolver.py` - 8 tests for Word/Excel/PDF resolution and cross-check logic
- `src/models.py` - AnswerPayload.xpath and .mode changed to Optional with None defaults

## Decisions Made
- Lazy imports inside resolve_pair_ids() to avoid loading word_indexer/excel_indexer/pdf_indexer at module level (prevents unnecessary heavy imports when only one file type is needed)
- Resolver returns dict omitting missing pair_ids (caller checks for missing) rather than raising ValueError -- this matches the existing pattern where not-found is a data condition, not an error

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- pair_id_resolver.py is ready to be called from tool_errors.py (Plan 02)
- AnswerPayload now accepts xpath=None and mode=None, enabling the minimal payload pattern
- Plan 02 will wire resolution into the write path and add warnings to response

## Self-Check: PASSED

- [x] src/pair_id_resolver.py exists
- [x] tests/test_pair_id_resolver.py exists
- [x] Commit 5b7e120 exists (Task 1)
- [x] Commit da2e18f exists (Task 2)
- [x] 289 tests pass (281 existing + 8 new)

---
*Phase: 08-resolution-infrastructure*
*Completed: 2026-02-17*
