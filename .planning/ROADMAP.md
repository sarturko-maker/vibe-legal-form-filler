# Roadmap: Vibe Legal Form Filler — Cross-Platform Transport

## Overview

This milestone adds HTTP transport to an existing stdio-based MCP server, enabling cross-platform AI agent integration while preserving the working stdio mode. The journey starts with transport setup (flag-based switching), then adds protocol compliance (header validation, error responses), validates correctness through HTTP integration testing, and finishes with cross-platform verification (Gemini CLI, Antigravity). All 172 existing tests must continue passing, and the server must work identically over both transports.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Transport Setup** - Add HTTP transport mode via --http flag, preserve stdio
- [x] **Phase 2: Protocol Implementation** - Add MCP HTTP protocol compliance (headers, errors, version negotiation) (completed 2026-02-16)
- [x] **Phase 3: HTTP Integration Testing** - Comprehensive HTTP transport test suite with real server startup (completed 2026-02-16)
- [ ] **Phase 4: Cross-Platform Verification** - Verify compatibility with Gemini CLI and Antigravity, document setup

## Phase Details

### Phase 1: Transport Setup
**Goal**: Server supports both stdio and HTTP modes via runtime flag with no behavioral differences in tool execution
**Depends on**: Nothing (first phase)
**Requirements**: TRANS-01, TRANS-02, TRANS-07
**Success Criteria** (what must be TRUE):
  1. User can start server in stdio mode (default) and all existing functionality works unchanged
  2. User can start server with --http flag and server binds to 127.0.0.1:8000
  3. All 172 existing unit tests pass without modification (stdio mode validation)
  4. All 6 MCP tools are available in both transports (tool registration works identically)
**Plans:** 1 plan
- [ ] 01-01-PLAN.md — CLI parsing, HTTP transport runner, entry points, test verification

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
- [ ] 02-01-PLAN.md — Custom 404 handler and protocol compliance tests (TRANS-03/04/05/06)

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
- [ ] 03-01-PLAN.md — Shared HTTP test fixtures (conftest.py), refactor protocol tests, transport parity tests for all 6 core tools (TEST-01, TEST-02)
- [ ] 03-02-PLAN.md — Utility tool HTTP tests, deeper error scenarios, concurrent request tests (TEST-03, TEST-04, TEST-05)

### Phase 4: Cross-Platform Verification
**Goal**: Verified compatibility with Gemini CLI and Antigravity platforms with documented setup procedures
**Depends on**: Phase 3
**Requirements**: XPLAT-01, XPLAT-02, XPLAT-03, XPLAT-04, DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Success Criteria** (what must be TRUE):
  1. Gemini CLI successfully connects to HTTP server and discovers all 6 tools plus utilities
  2. Gemini CLI completes full questionnaire pipeline (extract → validate → build → write → verify) with a sample form
  3. Antigravity successfully connects to HTTP server and discovers all tools
  4. Antigravity completes full questionnaire pipeline with a sample form
  5. Documentation exists for HTTP transport usage (startup, port, flags), Claude Code setup confirmation, Gemini CLI setup, and Antigravity setup
**Plans:** 2 plans
Plans:
- [ ] 04-01-PLAN.md — Create setup documentation for HTTP transport, Claude Code, Gemini CLI, and Antigravity
- [ ] 04-02-PLAN.md — Configure and verify Gemini CLI and Antigravity HTTP connectivity and pipeline

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Transport Setup | 0/1 | Not started | - |
| 2. Protocol Implementation | 0/1 | Complete    | 2026-02-16 |
| 3. HTTP Integration Testing | 0/2 | Complete    | 2026-02-16 |
| 4. Cross-Platform Verification | 0/2 | Not started | - |
