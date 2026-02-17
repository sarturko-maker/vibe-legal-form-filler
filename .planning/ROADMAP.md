# Roadmap: Vibe Legal Form Filler

## Milestones

- v1.0 Cross-Platform Transport -- Phases 1-4 (shipped 2026-02-17)
- v2.0 Performance Optimization -- Phases 5-7 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, ...): Planned milestone work
- Decimal phases (5.1, 5.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Cross-Platform Transport (Phases 1-4) -- SHIPPED 2026-02-17</summary>

- [x] **Phase 1: Transport Setup** - Add HTTP transport mode via --http flag, preserve stdio
- [x] **Phase 2: Protocol Implementation** - Add MCP HTTP protocol compliance (headers, errors, version negotiation)
- [x] **Phase 3: HTTP Integration Testing** - Comprehensive HTTP transport test suite with real server startup
- [x] **Phase 4: Cross-Platform Verification** - Verify compatibility with Gemini CLI and Antigravity, document setup

</details>

### v2.0 Performance Optimization (Phases 5-7)

**Milestone Goal:** Reduce MCP round-trips so a 30-question Word questionnaire completes in minutes instead of 10+, by eliminating the per-answer build_insertion_xml bottleneck.

- [ ] **Phase 5: Fast Path Foundation** - Add answer_text field, formatting extraction function, validation, backward compatibility
- [ ] **Phase 6: Fast Path Implementation** - Server builds insertion OOXML inline during write_answers for all insertion modes
- [ ] **Phase 7: Verification and Documentation** - Parity tests, edge-case coverage, regression pass, agent guidance

## Phase Details

<details>
<summary>v1.0 Phase Details (completed)</summary>

### Phase 1: Transport Setup
**Goal**: Server supports both stdio and HTTP modes via runtime flag with no behavioral differences in tool execution
**Depends on**: Nothing (first phase)
**Requirements**: TRANS-01, TRANS-02, TRANS-07
**Success Criteria** (what must be TRUE):
  1. User can start server in stdio mode (default) and all existing functionality works unchanged
  2. User can start server with --http flag and server binds to 127.0.0.1:8000
  3. All 172 existing unit tests pass without modification (stdio mode validation)
  4. All 6 MCP tools are available in both transports (tool registration works identically)
**Plans:** 1/1 plans complete
- [x] 01-01-PLAN.md -- CLI parsing, HTTP transport runner, entry points, test verification

### Phase 2: Protocol Implementation
**Goal**: HTTP transport meets full MCP protocol compliance with proper header validation and error handling
**Depends on**: Phase 1
**Requirements**: TRANS-03, TRANS-04, TRANS-05, TRANS-06
**Success Criteria** (what must be TRUE):
  1. Server accepts POST requests with JSON-RPC 2.0 bodies and returns proper responses
  2. Server validates MCP-Protocol-Version header and returns 400 with clear error on mismatch
  3. Server validates Origin header to prevent DNS rebinding attacks
  4. Server returns proper HTTP error responses (400/404/405/406) with JSON-RPC error bodies for invalid requests
  5. Server handles Accept header variations (strict compliance for production, wildcards accepted for localhost v1)
**Plans:** 1/1 plans complete
- [x] 02-01-PLAN.md -- Custom 404 handler and protocol compliance tests (TRANS-03/04/05/06)

### Phase 3: HTTP Integration Testing
**Goal**: Comprehensive test coverage proving HTTP transport correctness and transport parity
**Depends on**: Phase 2
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. All 172 existing unit tests continue passing after HTTP code changes
  2. Integration tests confirm all 6 MCP tools produce identical results when called via stdio vs HTTP
  3. Integration tests confirm utility tools (extract_text, list_form_fields) work correctly over HTTP
  4. HTTP-specific error tests confirm proper responses (406 for wrong Accept, 400 for malformed JSON-RPC, 404 for wrong path)
  5. Concurrent request tests confirm stateless design handles multiple simultaneous HTTP requests
**Plans:** 2/2 plans complete
- [x] 03-01-PLAN.md -- Shared HTTP test fixtures (conftest.py), refactor protocol tests, transport parity tests for all 6 core tools (TEST-01, TEST-02)
- [x] 03-02-PLAN.md -- Utility tool HTTP tests, deeper error scenarios, concurrent request tests (TEST-03, TEST-04, TEST-05)

### Phase 4: Cross-Platform Verification
**Goal**: Verified compatibility with Gemini CLI and Antigravity platforms with documented setup procedures
**Depends on**: Phase 3
**Requirements**: XPLAT-01, XPLAT-02, XPLAT-03, XPLAT-04, DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Success Criteria** (what must be TRUE):
  1. Gemini CLI successfully connects to HTTP server and discovers all 6 tools plus utilities
  2. Gemini CLI completes full questionnaire pipeline (extract, validate, build, write, verify) with a sample form
  3. Antigravity successfully connects to HTTP server and discovers all tools
  4. Antigravity completes full questionnaire pipeline with a sample form
  5. Documentation exists for HTTP transport usage (startup, port, flags), Claude Code setup confirmation, Gemini CLI setup, and Antigravity setup
**Plans:** 2/2 plans complete
- [x] 04-01-PLAN.md -- Create setup documentation for HTTP transport, Claude Code, Gemini CLI, and Antigravity
- [x] 04-02-PLAN.md -- Configure and verify Gemini CLI and Antigravity HTTP connectivity and pipeline

</details>

### Phase 5: Fast Path Foundation
**Goal**: The API contract for answer_text is defined, formatting extraction is available as a public function, and validation enforces correct usage -- all without changing the write path yet
**Depends on**: Phase 4 (v1.0 complete)
**Requirements**: FAST-04, FAST-05, COMPAT-01, COMPAT-02
**Success Criteria** (what must be TRUE):
  1. `extract_formatting_from_element()` exists as a public function in xml_formatting.py and returns the same formatting properties as `extract_formatting()` when given an lxml element
  2. `AnswerPayload` model accepts an optional `answer_text` field alongside `insertion_xml`, with both defaulting to empty string
  3. Validation rejects answers that provide neither `answer_text` nor `insertion_xml`, returning a clear error message that names both fields
  4. Existing agents using `insertion_xml` alone continue working with zero changes (all 234 tests pass)
  5. An answer payload containing both `answer_text` and `insertion_xml` in the same write_answers call is accepted (mixed mode)
**Plans**: TBD

### Phase 6: Fast Path Implementation
**Goal**: The server builds insertion OOXML internally during write_answers when answer_text is provided, eliminating the need for agents to call build_insertion_xml for plain-text answers
**Depends on**: Phase 5
**Requirements**: FAST-01, FAST-02, FAST-03
**Success Criteria** (what must be TRUE):
  1. Agent can call write_answers with `answer_text` (no `insertion_xml`) and the answer appears in the output document with correct formatting
  2. The inserted text inherits font family, font size, bold, italic, and color from the target element -- identical to what build_insertion_xml would have produced
  3. All three insertion modes (replace_content, append, replace_placeholder) work with answer_text
  4. A 30-answer write_answers call with answer_text completes without the agent ever calling build_insertion_xml
**Plans**: TBD

### Phase 7: Verification and Documentation
**Goal**: Proven correctness of the fast path through parity and edge-case tests, with updated agent guidance so callers adopt the new path
**Depends on**: Phase 6
**Requirements**: QA-01, QA-02, QA-03, DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):
  1. A parity test runs both paths (answer_text fast path vs build_insertion_xml + insertion_xml) on the same fixture data and confirms byte-identical output
  2. Edge-case tests cover leading/trailing spaces, XML special characters (&, <, >, quotes), and empty string answer_text
  3. All 234 existing tests pass after the complete v2.0 changes (zero regressions)
  4. CLAUDE.md pipeline documentation shows answer_text as the preferred path for plain-text Word answers, with insertion_xml as the fallback for structured answers
  5. Agent guidance section in CLAUDE.md explains when to use answer_text vs insertion_xml with a clear decision rule

## Progress

**Execution Order:**
Phases execute in numeric order: 5 -> 6 -> 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Transport Setup | v1.0 | 1/1 | Complete | 2026-02-17 |
| 2. Protocol Implementation | v1.0 | 1/1 | Complete | 2026-02-16 |
| 3. HTTP Integration Testing | v1.0 | 2/2 | Complete | 2026-02-16 |
| 4. Cross-Platform Verification | v1.0 | 2/2 | Complete | 2026-02-17 |
| 5. Fast Path Foundation | v2.0 | 0/? | Not started | - |
| 6. Fast Path Implementation | v2.0 | 0/? | Not started | - |
| 7. Verification and Documentation | v2.0 | 0/? | Not started | - |
