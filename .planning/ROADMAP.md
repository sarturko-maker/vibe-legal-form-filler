# Roadmap: Vibe Legal Form Filler

## Milestones

- v1.0 Cross-Platform Transport -- Phases 1-4 (shipped 2026-02-17)
- v2.0 Performance Optimization -- Phases 5-6 (shipped 2026-02-17, Phase 7 absorbed into v2.1)
- v2.1 Gemini Consolidation -- Phases 8-11 (in progress)

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

<details>
<summary>v2.0 Performance Optimization (Phases 5-6) -- SHIPPED 2026-02-17</summary>

- [x] **Phase 5: Fast Path Foundation** - Add answer_text field, formatting extraction function, validation, backward compatibility
- [x] **Phase 6: Fast Path Implementation** - Server builds insertion OOXML inline during write_answers for all insertion modes

</details>

### v2.1 Gemini Consolidation (Phases 8-11)

**Milestone Goal:** Fix cross-platform agent ergonomics issues discovered during Gemini CLI testing — make the fast path truly zero-friction by resolving xpaths from pair_ids, defaulting modes, handling skips, and updating pipeline guidance.

- [x] **Phase 8: Resolution Infrastructure** - pair_id→xpath resolution via re-extraction for write_answers, cross-check validation (completed 2026-02-17)
- [x] **Phase 9: Ergonomics & Tolerance** - file_path echo, improved error messages, SKIP convention, mode defaults (completed 2026-02-17)
- [ ] **Phase 10: Verification Parity** - verify_output accepts pair_id without xpath, cross-check logic
- [ ] **Phase 11: Documentation & QA** - CLAUDE.md pipeline updates, test coverage, regression validation

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

<details>
<summary>v2.0 Phase Details (completed)</summary>

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
**Plans:** 2/2 plans complete
- [x] 05-01-PLAN.md -- Model field changes (answer_text on AnswerPayload), extract_formatting_from_element function, parity tests
- [x] 05-02-PLAN.md -- Batch validation logic (exactly-one-of semantics, error aggregation), integration tests

### Phase 6: Fast Path Implementation
**Goal**: The server builds insertion OOXML internally during write_answers when answer_text is provided, eliminating the need for agents to call build_insertion_xml for plain-text answers
**Depends on**: Phase 5
**Requirements**: FAST-01, FAST-02, FAST-03
**Success Criteria** (what must be TRUE):
  1. Agent can call write_answers with `answer_text` (no `insertion_xml`) and the answer appears in the output document with correct formatting
  2. The inserted text inherits font family, font size, bold, italic, and color from the target element -- identical to what build_insertion_xml would have produced
  3. All three insertion modes (replace_content, append, replace_placeholder) work with answer_text
  4. A 30-answer write_answers call with answer_text completes without the agent ever calling build_insertion_xml
**Plans:** 1/1 plans complete
- [x] 06-01-PLAN.md -- Fast path helper, routing in _apply_answer, tests for all three modes

</details>

### Phase 8: Resolution Infrastructure
**Goal**: The server resolves xpaths from pair_ids via re-extraction so agents don't need to carry xpaths through the pipeline, with cross-checking when both are provided
**Depends on**: Phase 6 (v2.0 complete)
**Requirements**: ERG-03, ERG-04, ERG-05
**Success Criteria** (what must be TRUE):
  1. Agent can call write_answers with pair_id and answer_text only (no xpath, no mode) and the answer is written correctly
  2. Server re-extracts compact structure to resolve pair_id→xpath when xpath is not provided
  3. When both xpath and pair_id are provided, server cross-checks and warns on mismatch (pair_id is authority)
  4. Cross-check warnings are logged but do not block writes (warning in response metadata)
  5. Resolution infrastructure reuses existing id_to_xpath logic from word_location_validator.py
**Plans:** 2/2 plans complete
- [ ] 08-01-PLAN.md -- Create pair_id_resolver module, make AnswerPayload xpath/mode optional (TDD)
- [ ] 08-02-PLAN.md -- Wire resolution into write path, add cross-check warnings, E2E tests

### Phase 9: Ergonomics & Tolerance
**Goal**: Small API improvements that reduce agent friction — file_path echo, better errors, SKIP convention, mode defaults
**Depends on**: Phase 8
**Requirements**: ERG-01, ERG-02, TOL-01, TOL-02
**Success Criteria** (what must be TRUE):
  1. extract_structure_compact response includes file_path when provided as input (agent doesn't need to track it separately)
  2. write_answers error for missing file says "Missing file_path -- this is the path you passed to extract_structure_compact"
  3. answer_text="SKIP" is recognized as intentional skip (no write, status="skipped" in response)
  4. Skipped fields are reported in write_answers summary with count (e.g., "42 written, 3 skipped")
  5. mode defaults to replace_content when answer_text is provided and mode is omitted
**Plans:** 1/1 plans complete
Plans:
- [ ] 09-01-PLAN.md -- file_path echo, write_answers error, SKIP convention, response summary

### Phase 10: Verification Parity
**Goal**: verify_output accepts pair_id without xpath, matching the write_answers capability so agents use the same identifiers for both tools
**Depends on**: Phase 8
**Requirements**: VER-01, VER-02
**Success Criteria** (what must be TRUE):
  1. Agent can call verify_output with pair_id only (no xpath) and content verification works correctly
  2. Server resolves pair_id→xpath via re-extraction using the same logic as write_answers
  3. When both xpath and pair_id are provided, server cross-checks and warns on mismatch
  4. verify_output response includes resolution metadata (resolved_from="pair_id" or "xpath")
**Plans:** 1 plan
Plans:
- [ ] 10-01-PLAN.md -- Model changes, resolution-aware validation, verify_output wiring, E2E tests

### Phase 11: Documentation & QA
**Goal**: CLAUDE.md reflects new simplified API, all tests pass, new test coverage added for v2.1 features
**Depends on**: Phase 9, Phase 10
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, QA-01, QA-02, QA-03, QA-04
**Success Criteria** (what must be TRUE):
  1. CLAUDE.md pipeline includes style review step between write and verify
  2. CLAUDE.md documents SKIP convention for intentionally blank fields (signatures, dates)
  3. All tool docstrings updated with new optional parameters (pair_id, SKIP, mode defaults)
  4. CLAUDE.md agent guidance documents simplified fast-path parameter set (pair_id + answer_text only)
  5. All 281 existing tests pass after v2.1 changes
  6. New tests for pair_id→xpath resolution in write_answers exist and pass
  7. New tests for SKIP handling exist and pass
  8. New tests for verify_output with pair_id only exist and pass
**Plans**: TBD

## Progress

**Execution Order:**
- v1.0: Phases 1 → 2 → 3 → 4 (complete)
- v2.0: Phases 5 → 6 (complete)
- v2.1: Phases 8 → 9 → 10 → 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Transport Setup | v1.0 | 1/1 | Complete | 2026-02-17 |
| 2. Protocol Implementation | v1.0 | 1/1 | Complete | 2026-02-16 |
| 3. HTTP Integration Testing | v1.0 | 2/2 | Complete | 2026-02-16 |
| 4. Cross-Platform Verification | v1.0 | 2/2 | Complete | 2026-02-17 |
| 5. Fast Path Foundation | v2.0 | 2/2 | Complete | 2026-02-17 |
| 6. Fast Path Implementation | v2.0 | 1/1 | Complete | 2026-02-17 |
| 8. Resolution Infrastructure | v2.1 | Complete    | 2026-02-17 | - |
| 9. Ergonomics & Tolerance | v2.1 | Complete    | 2026-02-17 | - |
| 10. Verification Parity | v2.1 | 0/? | Not started | - |
| 11. Documentation & QA | v2.1 | 0/? | Not started | - |
