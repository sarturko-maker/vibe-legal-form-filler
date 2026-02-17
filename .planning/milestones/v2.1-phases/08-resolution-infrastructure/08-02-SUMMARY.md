---
phase: 08-resolution-infrastructure
plan: 02
subsystem: api
tags: [resolution, pair-id, xpath, cross-check, write-answers, warnings]

# Dependency graph
requires:
  - phase: 08-resolution-infrastructure
    plan: 01
    provides: "pair_id_resolver module with resolve_pair_ids() and cross_check_xpaths()"
provides:
  - "write_answers accepts pair_id + answer_text only (no xpath, no mode required)"
  - "Resolution pipeline wired into build_answer_payloads via file_bytes passthrough"
  - "Cross-check warnings in write_answers response dict"
  - "resolve_if_needed and infer_relaxed_file_type helpers in pair_id_resolver"
affects: [tools_write, tool_errors, pair_id_resolver]

# Tech tracking
tech-stack:
  added: []
  patterns: ["tuple return (payloads, warnings) from build_answer_payloads", "per-answer context-dependent validation (answer_text vs insertion_xml)"]

key-files:
  created: ["tests/test_resolution.py"]
  modified: ["src/tool_errors.py", "src/tools_write.py", "src/pair_id_resolver.py", "tests/test_e2e_integration.py"]

key-decisions:
  - "Relaxed path (Excel/PDF) uses pair_id as xpath directly instead of re-extraction (pair_id IS the element ID)"
  - "Cross-check only triggers on Word path where xpath and pair_id are distinct identifier systems"
  - "Extracted resolve_if_needed to pair_id_resolver.py to keep tool_errors.py focused"

patterns-established:
  - "Per-answer validation: answer_text path allows optional xpath/mode; insertion_xml path requires both"
  - "Warnings-in-response pattern: non-empty warnings list attached to write_answers response dict"

requirements-completed: [ERG-03, ERG-04, ERG-05]

# Metrics
duration: 8min
completed: 2026-02-17
---

# Phase 8 Plan 2: Resolution Integration Summary

**pair_id-only write_answers with automatic xpath resolution, mode defaulting, and cross-check warnings**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-17T14:05:29Z
- **Completed:** 2026-02-17T14:13:30Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Agents can now call write_answers with just `{pair_id: "T1-R2-C2", answer_text: "Acme Corp"}` -- no xpath or mode needed
- Server re-extracts compact structure to resolve pair_id to xpath automatically
- Mode defaults to replace_content when answer_text is provided and mode is omitted
- Cross-check warnings appear in the response when agent xpath disagrees with resolved xpath (pair_id is authority)
- insertion_xml path unchanged: still requires explicit xpath and mode (backward compatible)
- All 295 tests pass (289 existing + 6 new resolution tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Integrate resolution into tool_errors.py and tools_write.py** - `a56aa54` (feat)
2. **Task 2: Add E2E tests for pair_id-only write_answers** - `a3ec66d` (test)

## Files Created/Modified
- `src/tool_errors.py` - build_answer_payloads accepts file_bytes, returns (payloads, warnings); per-answer context-dependent validation
- `src/tools_write.py` - Passes raw bytes to build_answer_payloads; includes warnings in response dict
- `src/pair_id_resolver.py` - Added resolve_if_needed() and infer_relaxed_file_type() helpers
- `tests/test_e2e_integration.py` - Updated 4 existing tests for tuple return type
- `tests/test_resolution.py` - 6 new E2E tests for pair_id-only writes, cross-check warnings, error cases

## Decisions Made
- Relaxed path (Excel/PDF) uses pair_id directly as xpath rather than re-extracting: on these paths, pair_id IS the element ID (S1-R2-C2 for Excel, F1 for PDF), so re-extraction would return the native field name which is a different identifier system
- Cross-check warnings only on Word path where agent xpath and pair_id point to different things (Word xpaths are XPath expressions like ./w:tbl[1]/w:tr[2]/w:tc[2], distinct from pair_ids like T1-R2-C2)
- Extracted `resolve_if_needed` to pair_id_resolver.py to keep tool_errors.py focused on validation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed relaxed path xpath resolution breaking PDF writes**
- **Found during:** Task 1
- **Issue:** Cross-check replaced PDF xpath (F1) with resolved native field name (full_name), but PDF writer expects field IDs as xpath
- **Fix:** Relaxed path (Excel/PDF) uses pair_id directly as xpath instead of re-extraction; cross-check only on Word path
- **Files modified:** src/tool_errors.py
- **Verification:** All 289 existing tests pass including PDF pipeline test
- **Committed in:** a56aa54 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Bug found and fixed during implementation. The relaxed path design is cleaner than the plan's suggestion because it avoids unnecessary re-extraction.

## Issues Encountered
- tool_errors.py grew to 420 lines (above 370 guideline). Resolution helpers were extracted to pair_id_resolver.py as the plan suggested. Remaining growth is from per-answer context-dependent validation logic which is inherent to the feature.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 8 complete: both resolver module (Plan 01) and integration (Plan 02) are done
- Agents can now use the simplified payload: `{pair_id, answer_text}` for all three file types
- Full backward compatibility maintained: insertion_xml + xpath + mode still works

## Self-Check: PASSED

- [x] src/tool_errors.py updated with resolution integration
- [x] src/tools_write.py updated with warnings in response
- [x] src/pair_id_resolver.py updated with resolve_if_needed helper
- [x] tests/test_resolution.py created with 6 tests
- [x] Commit a56aa54 exists (Task 1)
- [x] Commit a3ec66d exists (Task 2)
- [x] 295 tests pass (289 existing + 6 new)

---
*Phase: 08-resolution-infrastructure*
*Completed: 2026-02-17*
