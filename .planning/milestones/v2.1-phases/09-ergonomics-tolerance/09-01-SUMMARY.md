---
phase: 09-ergonomics-tolerance
plan: 01
subsystem: api
tags: [mcp, ergonomics, tolerance, skip-convention, error-messages]

# Dependency graph
requires:
  - phase: 08-resolution-infrastructure
    provides: pair_id resolution pipeline and build_answer_payloads
provides:
  - file_path echo in extract_structure_compact response
  - write_answers-specific error message for missing file_path
  - SKIP sentinel detection and filtering in write_answers
  - summary dict with written/skipped counts in write_answers response
affects: [10-agent-documentation, 11-qa-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns: [dict-injection after model_dump for response augmentation, sentinel value filtering at tool level before handler dispatch]

key-files:
  created:
    - tests/test_ergonomics.py
  modified:
    - src/tools_extract.py
    - src/tool_errors.py
    - src/tools_write.py

key-decisions:
  - "Dict injection after model_dump() rather than adding file_path to Pydantic model -- avoids changing three indexer functions"
  - "SKIP filtering at tools_write.py level after build_answer_payloads -- keeps validation and routing concerns separate"
  - "Summary always present in response (even when skipped=0) for consistent agent parsing"

patterns-established:
  - "Response augmentation: add tool-level fields to dict after model_dump() rather than modifying internal models"
  - "Sentinel filtering: detect special answer values at the tool layer, never pass them to format handlers"

requirements-completed: [ERG-01, ERG-02, TOL-01, TOL-02]

# Metrics
duration: 3min
completed: 2026-02-17
---

# Phase 9 Plan 01: Ergonomics & Tolerance Summary

**file_path echo in extract responses, write_answers-specific error messages, SKIP sentinel filtering with summary counts**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-17T14:34:14Z
- **Completed:** 2026-02-17T14:36:58Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- extract_structure_compact echoes file_path in response when provided as input (omits when using b64)
- write_answers error for missing file says "Missing file_path -- this is the path you passed to extract_structure_compact"
- answer_text="SKIP" (case-insensitive) recognized as intentional skip: no write, included in dry_run with status="skipped"
- write_answers response always includes summary dict with written and skipped counts
- All-SKIP edge case returns original file bytes unchanged
- 11 new tests, 306 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add file_path echo and write_answers error message** - `133ea98` (feat)
2. **Task 2: Implement SKIP convention and response summary** - `13db416` (feat)

## Files Created/Modified
- `src/tools_extract.py` - Refactored extract_structure_compact to assign-then-return pattern; injects file_path into result dict
- `src/tool_errors.py` - Added write_answers-specific error message in resolve_file_for_tool
- `src/tools_write.py` - Added _is_skip helper, SKIP filtering, summary dict, dry_run SKIP entries
- `tests/test_ergonomics.py` - 11 tests covering all four requirements

## Decisions Made
- Used dict injection after model_dump() for file_path echo rather than modifying the CompactStructureResponse Pydantic model -- avoids changing three indexer functions (word/excel/pdf) that do not need to know about file_path
- SKIP filtering at tools_write.py level after build_answer_payloads() returns -- keeps validation (tool_errors.py) and routing (tools_write.py) concerns separate
- Summary always present in response even when skipped=0 for consistent agent parsing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 306 tests passing (295 existing + 11 new)
- API is more self-describing and forgiving for agents
- Ready for Phase 10 (agent documentation) or Phase 11 (QA hardening)

## Self-Check: PASSED

- All 5 key files exist on disk
- Both task commits (133ea98, 13db416) found in git log
- 306 tests collected and passing

---
*Phase: 09-ergonomics-tolerance*
*Completed: 2026-02-17*
