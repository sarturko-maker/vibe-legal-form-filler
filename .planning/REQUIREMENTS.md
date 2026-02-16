# Requirements: Vibe Legal Form Filler — Cross-Platform Transport

**Defined:** 2026-02-16
**Core Value:** The server must work identically over both stdio and HTTP transports — same tools, same inputs, same outputs

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Transport

- [ ] **TRANS-01**: Server accepts `--http` flag to start in Streamable HTTP mode (default remains stdio)
- [ ] **TRANS-02**: HTTP mode binds to localhost (127.0.0.1) only
- [ ] **TRANS-03**: HTTP endpoint accepts JSON-RPC 2.0 requests via POST
- [ ] **TRANS-04**: Server validates MCP-Protocol-Version header on HTTP requests
- [ ] **TRANS-05**: Server validates Origin header to prevent DNS rebinding attacks
- [ ] **TRANS-06**: Server returns graceful HTTP error responses (400/404/405) with JSON-RPC error bodies
- [ ] **TRANS-07**: Stdio transport continues working exactly as before (no behavioral changes)

### Testing

- [ ] **TEST-01**: All 172 existing unit tests pass after transport changes
- [ ] **TEST-02**: Integration tests confirm all 6 MCP tools produce identical results over stdio and HTTP
- [ ] **TEST-03**: Integration tests confirm utilities (extract_text, list_form_fields) work over HTTP
- [ ] **TEST-04**: HTTP-specific tests for error responses (406 for wrong Accept header, 400 for malformed JSON-RPC, 404 for wrong path)
- [ ] **TEST-05**: HTTP-specific tests for concurrent requests (statelessness verification)

### Cross-Platform

- [ ] **XPLAT-01**: Gemini CLI successfully connects to the server and discovers all tools
- [ ] **XPLAT-02**: Gemini CLI completes a full questionnaire pipeline (extract → validate → build XML → write → verify)
- [ ] **XPLAT-03**: Antigravity successfully connects to the server and discovers all tools
- [ ] **XPLAT-04**: Antigravity completes a full questionnaire pipeline (extract → validate → build XML → write → verify)

### Documentation

- [ ] **DOCS-01**: HTTP transport usage documentation (how to start, port configuration, transport flag)
- [ ] **DOCS-02**: Claude Code setup guide (stdio — existing config, confirm still works)
- [ ] **DOCS-03**: Gemini CLI setup guide (connection config, tested commands)
- [ ] **DOCS-04**: Antigravity setup guide (connection config, tested commands)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Security

- **SEC-01**: API key authentication for HTTP transport (enterprise deployment behind corporate networks)
- **SEC-02**: Configurable CORS policies for non-localhost deployments

### Enterprise Integration

- **ENT-01**: Microsoft Copilot Studio connection and tool discovery
- **ENT-02**: Copilot Studio completes full questionnaire pipeline
- **ENT-03**: Network deployment (bind to 0.0.0.0 with authentication)

### Advanced Transport

- **ADV-01**: SSE stream support for long-running operations
- **ADV-02**: Health check endpoint for monitoring
- **ADV-03**: Request logging middleware

## Out of Scope

| Feature | Reason |
|---------|--------|
| Node.js rewrite | Python only — existing codebase, existing tests, existing expertise |
| Docker containerization | Runs locally on Chromebook, no container runtime needed |
| Web UI or REST API | MCP protocol only — agents are the clients |
| WebSocket transport | Not in MCP spec; Streamable HTTP is the standard |
| Rate limiting | No abuse threat model for localhost-only personal use |
| Multi-worker deployment | Single-user Chromebook; horizontal scaling is v2+ |
| Changes to core document processing | Transport layer only — handlers, validators, models unchanged |
| SSE-only transport | Deprecated since August 2025; Streamable HTTP replaces it |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRANS-01 | Phase 1 | Pending |
| TRANS-02 | Phase 1 | Pending |
| TRANS-03 | Phase 2 | Pending |
| TRANS-04 | Phase 2 | Pending |
| TRANS-05 | Phase 2 | Pending |
| TRANS-06 | Phase 2 | Pending |
| TRANS-07 | Phase 1 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 3 | Pending |
| TEST-04 | Phase 3 | Pending |
| TEST-05 | Phase 3 | Pending |
| XPLAT-01 | Phase 4 | Pending |
| XPLAT-02 | Phase 4 | Pending |
| XPLAT-03 | Phase 4 | Pending |
| XPLAT-04 | Phase 4 | Pending |
| DOCS-01 | Phase 4 | Pending |
| DOCS-02 | Phase 4 | Pending |
| DOCS-03 | Phase 4 | Pending |
| DOCS-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0

---
*Requirements defined: 2026-02-16*
*Last updated: 2026-02-16 after roadmap creation*
