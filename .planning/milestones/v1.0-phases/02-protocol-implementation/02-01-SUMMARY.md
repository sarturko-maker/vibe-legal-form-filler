---
phase: 02-protocol-implementation
plan: 01
subsystem: infra
tags: [starlette, json-rpc, protocol-compliance, mcp-http, dns-rebinding, testclient]

# Dependency graph
requires:
  - phase: 01-transport-setup
    provides: "Custom uvicorn runner wrapping mcp.streamable_http_app()"
provides:
  - "JSON-RPC 404 error handler for Starlette app"
  - "Protocol compliance test suite covering TRANS-03/04/05/06"
  - "Session manager reset pattern for TestClient-based HTTP tests"
affects: [03-testing, 04-cross-platform]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Starlette exception_handlers[404] for JSON-RPC error bodies", "Session manager reset between TestClient tests"]

key-files:
  created: [tests/test_http_protocol.py]
  modified: [src/http_transport.py]

key-decisions:
  - "Session manager must be reset (mcp._session_manager = None) before each TestClient test -- StreamableHTTPSessionManager.run() can only be called once per instance"
  - "Invalid-origin test uses its own fresh TestClient since the mcp_client fixture initializes a session which fails when origin is blocked"

patterns-established:
  - "_fresh_app() helper + autouse _reset_session_manager fixture for HTTP protocol testing"
  - "INIT_BODY + MCP_HEADERS constants shared across all protocol tests"

requirements-completed: [TRANS-03, TRANS-04, TRANS-05, TRANS-06]

# Metrics
duration: 3min
completed: 2026-02-16
---

# Phase 2 Plan 1: Protocol Implementation Summary

**Custom JSON-RPC 404 handler closing the only SDK compliance gap, plus 10 protocol tests verifying TRANS-03/04/05/06 via Starlette TestClient**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-16T22:53:27Z
- **Completed:** 2026-02-16T22:56:54Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Custom `_json_rpc_404_handler` in http_transport.py returns JSON-RPC error body instead of Starlette's plain-text default for wrong paths
- 10 protocol compliance tests covering all four TRANS requirements (JSON-RPC requests, version validation, origin validation, error responses)
- All 217 tests pass (207 existing + 10 new) with zero regressions
- Both files well under 200-line limit (http_transport.py: 108, test_http_protocol.py: 189)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add custom JSON-RPC 404 handler** - `842b8d0` (feat)
2. **Task 2: Write protocol compliance tests** - `639c112` (test)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `src/http_transport.py` - Added `_json_rpc_404_handler` and attached it to Starlette app (88 -> 108 lines)
- `tests/test_http_protocol.py` - 10 protocol compliance tests using Starlette TestClient (189 lines)

## Decisions Made
- Session manager must be reset (`mcp._session_manager = None`) before each TestClient test because `StreamableHTTPSessionManager.run()` can only be called once per instance. Used an `autouse` fixture for cleanup plus `_fresh_app()` helper for app creation.
- Invalid-origin test (`test_invalid_origin_returns_403`) uses its own fresh TestClient rather than the `mcp_client` fixture, because the fixture performs an initialize handshake which would also fail with a bad origin.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Session manager single-use limitation**
- **Found during:** Task 2 (first test run)
- **Issue:** `StreamableHTTPSessionManager.run()` raises RuntimeError if called more than once. The `mcp_client` fixture called `mcp.streamable_http_app()` which reused the same session manager instance across test functions.
- **Fix:** Added `_fresh_app()` helper that sets `mcp._session_manager = None` before building the app, and an `autouse=True` `_reset_session_manager` fixture that cleans up after each test.
- **Files modified:** tests/test_http_protocol.py
- **Verification:** All 10 tests pass in sequence
- **Committed in:** 639c112 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary fix to make TestClient work across multiple test functions. No scope creep.

## Issues Encountered
- File initially at 214 lines (over 200-line limit). Condensed module docstring and removed extra blank lines between test functions to reach 189 lines.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All MCP protocol requirements (TRANS-03/04/05/06) verified and covered by tests
- Ready for Phase 3 testing or Phase 4 cross-platform verification
- Accept header wildcard handling (`*/*`) deferred to Phase 4 per research recommendations

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 02-protocol-implementation*
*Completed: 2026-02-16*
