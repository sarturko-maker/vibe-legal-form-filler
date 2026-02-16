# Project Research Summary

**Project:** vibe-legal-form-filler
**Domain:** MCP server dual-transport enhancement (stdio + HTTP)
**Researched:** 2026-02-16
**Confidence:** HIGH

## Executive Summary

Adding HTTP transport to an existing stdio-based MCP server is a minimal-change enhancement in 2026. The FastMCP framework provides native support for both transports through a single codebase with a runtime flag — no separate server implementations needed. All required dependencies (mcp 1.26.0, starlette 0.52.1, sse-starlette 3.2.0, uvicorn 0.40.0) are already installed in this project. The core architecture change is adding `--http` flag handling to `server.py` and calling `mcp.run(transport="streamable-http")` when triggered.

The recommended approach is transport-agnostic tools with flag-based switching. All existing business logic, tool definitions, and tests remain unchanged. HTTP transport adds value by enabling cross-platform AI agent integration (Gemini CLI, Antigravity, Copilot Studio) without sacrificing the working stdio mode used by Claude Code. The stateless design of existing tools eliminates session management complexity, making horizontal scaling possible in future phases.

Key risks are: (1) stdout pollution breaking stdio tests when developers add debug prints after testing HTTP, (2) strict Accept header validation causing 406 errors with some clients, and (3) transport-specific test gaps (existing 172 tests only cover stdio). Mitigations: enforce stderr-only logging via pre-commit hook, accept wildcard Accept headers for v1 localhost-only deployment, and add dedicated HTTP integration tests that exercise real server startup and concurrent requests.

## Key Findings

### Recommended Stack

The project already has all dependencies installed. No new packages required for basic HTTP transport. FastMCP 2.0+ natively supports both stdio and Streamable HTTP transports through the same codebase. The MCP SDK (v1.26.0+) includes StreamableHTTPSessionManager and all protocol compliance components. SSE transport is deprecated (August 2025) — Streamable HTTP is the 2026 standard.

**Core technologies:**
- **mcp (1.26.0)** — Official MCP SDK with built-in Streamable HTTP transport, already installed
- **starlette (0.52.1)** — ASGI framework for HTTP server, core dependency of MCP SDK, already installed
- **sse-starlette (3.2.0)** — Server-Sent Events for streaming responses, required by MCP SDK, already installed
- **uvicorn (0.40.0)** — ASGI server for production deployment, industry standard for FastAPI/Starlette in 2026, already installed

**No new packages required** — the stack is complete as-is.

### Expected Features

HTTP transport requires strict protocol compliance but most features are already implemented in FastMCP. The critical distinction is between table stakes (required for any MCP client to connect) and differentiators (competitive advantages specific to this server).

**Must have (table stakes):**
- Streamable HTTP POST endpoint — MCP spec mandates single endpoint for all client messages
- JSON-RPC 2.0 message format — universal MCP transport requirement, already implemented in FastMCP
- MCP-Protocol-Version header support — required by spec for HTTP transport
- Origin header validation — security requirement (DNS rebinding protection)
- Localhost binding (127.0.0.1) — security best practice for local servers
- Graceful error responses — HTTP 400/404/406 with JSON-RPC error bodies

**Should have (competitive):**
- Transport parity (stdio + HTTP) — same tools work identically across both transports, core value proposition
- Automatic transport detection — single entry point, mode flag chooses transport, better DX than separate binaries
- Stateless design — no session state between tool calls, simplifies HTTP implementation, enables horizontal scaling
- Large payload optimization — `answers_file_path` for writing >20 answers from JSON file, already implemented
- Detailed error context — rich error messages with file type, XPath, field IDs, already implemented

**Defer (v2+):**
- OAuth 2.1 authentication — standard for enterprise MCP servers, not needed for localhost v1
- API key authentication — fallback for platforms without OAuth support
- Rate limiting — per-client limits for multi-user environments
- SSE stream support — for platforms expecting streaming responses (long operations), optional for v1
- Session management (MCP-Session-Id) — only if platforms reject stateless servers, FastMCP provides this

### Architecture Approach

The standard MCP dual-transport architecture is transport-agnostic core with swappable transport layers. FastMCP handles all protocol compliance (JSON-RPC, headers, session management) — no custom transport code needed. Tools remain pure business logic with no transport dependencies. The project already follows this pattern: server.py imports tool modules (triggers import-time registration via @mcp.tool decorators), tool modules delegate to handlers (pure Python, no MCP dependencies), handlers call xml_utils/validators/models.

**Major components:**
1. **Transport Selection Layer** — runtime decision via CLI flag or env var, calls `mcp.run(transport="stdio"|"streamable-http")`
2. **FastMCP Core** — tool registration, routing, JSON-RPC handling, already implemented
3. **Tool Modules** — MCP tool definitions (@mcp.tool decorators), already implemented, no changes needed
4. **Business Logic Layer** — handlers, validators, xml_utils, models, already implemented, transport-agnostic

**Key architectural decision:** Single entry point with flag-based switching, not separate server files. Preserves working stdio mode while adding HTTP with one flag. All 172 existing tests run against stdio mode unchanged. HTTP integration tests added separately.

### Critical Pitfalls

Research identified 7 critical pitfalls, ranked by severity and likelihood:

1. **stdout Pollution Breaking stdio Tests** — Developers add debug prints while testing HTTP mode (where stdout is harmless), then existing stdio tests fail with "Invalid JSON-RPC message" because stdout must be pristine. Prevention: redirect all logging to stderr, add pre-commit hook to catch print statements, document "NEVER use stdout directly" in contribution guidelines.

2. **Missing Accept Header Causing 406 Errors** — MCP servers strictly enforce `Accept: application/json, text/event-stream` header. Clients sending `Accept: */*` or `Accept: application/json` only receive HTTP 406 Not Acceptable. Works with Claude Code but breaks with Gemini CLI or Antigravity. Prevention: for localhost-only v1, accept wildcard Accept headers per HTTP/1.1 spec, test with multiple clients before declaring compatibility.

3. **Session Management Confusion (Stateful vs Stateless)** — Developer implements stateful sessions with `Mcp-Session-Id` but then tries to scale horizontally with load balancing. Requests hit different instances, get HTTP 404 Not Found, client enters initialization loop. Prevention: for localhost-only v1, skip session management entirely (stateless=True in FastMCP), document "this server is stateless" clearly.

4. **Testing Only Happy Path, Not Transport-Specific Failures** — All 172 existing tests pass (they use stdio in-memory mode). Deploy to production. HTTP clients encounter Content-Type errors, missing headers, session validation issues. None were caught by tests. Prevention: add dedicated HTTP transport test suite with real server startup, test specific failure modes (406, 400, 404), mark as integration tests.

5. **Protocol Version Header Mismatch** — Client sends `MCP-Protocol-Version: 2025-06-18` but server only supports `2024-11-05`. Server returns 400 Bad Request or silently falls back. Connection fails or messages silently dropped. Prevention: validate MCP-Protocol-Version header on all HTTP requests, return 400 with clear error message, log both client and server versions.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Transport Setup
**Rationale:** Minimal code change (single file, ~15 lines), no new dependencies, preserves all existing functionality. Research shows FastMCP's flag-based transport selection requires only adding CLI argument parsing and conditional `mcp.run()` call. This must come first because it establishes the dual-transport foundation without breaking existing stdio tests.

**Delivers:** Server supports both stdio and HTTP modes via `--http` flag. Existing stdio functionality unchanged. HTTP server binds to 127.0.0.1:8000 by default (localhost-only for security).

**Addresses:**
- Streamable HTTP POST endpoint (table stakes)
- Transport parity foundation (competitive differentiator)
- Localhost binding (security best practice)
- Automatic transport detection (single entry point)

**Avoids:**
- stdout pollution (enforce stderr-only logging before any HTTP work)
- Session management confusion (choose stateless architecture upfront, document clearly)
- Hardcoded transport configuration (use CLI flag, not code edits)

### Phase 2: Protocol Implementation
**Rationale:** HTTP transport requires protocol compliance components (header validation, error responses, version negotiation). Research shows most are built into FastMCP but some need explicit configuration. Must come after transport setup so HTTP server exists to receive requests. Architecture research confirms transport-agnostic tools work unchanged — all changes are in protocol middleware.

**Delivers:** Full MCP HTTP protocol compliance. Header validation (Accept, MCP-Protocol-Version, Origin), graceful error responses with JSON-RPC bodies, protocol version negotiation, base64 encoding standardization.

**Uses:**
- mcp SDK (StreamableHTTPSessionManager, protocol version handling)
- starlette (middleware for header validation)
- sse-starlette (streaming response support if needed)

**Implements:**
- Header validation middleware (Accept header, MCP-Protocol-Version, Origin)
- Error response formatting (HTTP status codes + JSON-RPC error bodies)
- Base64 encoding wrapper (accept both standard and URL-safe variants)

**Avoids:**
- Missing Accept header causing 406 errors (accept wildcards for v1)
- Protocol version mismatch (validate and return clear error)
- Base64 encoding mismatch (accept both variants, output standard)

### Phase 3: HTTP Integration Testing
**Rationale:** Existing 172 tests only cover stdio transport. Research shows this is the #1 pitfall — tests pass but production HTTP clients fail because HTTP code paths are never exercised. Must come after protocol implementation so there's something to test. Pitfalls research emphasizes this phase prevents silent failures in production.

**Delivers:** Comprehensive HTTP transport test suite. Real server startup tests, concurrent request tests, failure mode tests (406, 400, 404), transport parity tests (stdio vs HTTP return identical results).

**Addresses:**
- Testing only happy path pitfall (dedicated HTTP failure mode tests)
- Transport parity verification (prove stdio and HTTP return identical tool results)

**Test categories:**
- Server lifecycle (startup, shutdown, port binding)
- Protocol compliance (header validation, version negotiation, error responses)
- Concurrent requests (stateless tool functions handle concurrency)
- Transport parity (same tool call via stdio and HTTP, compare byte-for-byte)

### Phase 4: Cross-Platform Testing
**Rationale:** Research shows client compatibility varies (Gemini CLI sends different Accept headers, Antigravity uses different config format). Must come after HTTP integration tests prove server works correctly. This phase validates real-world platform compatibility before declaring production-ready. Features research documents specific client requirements.

**Delivers:** Verified compatibility with Gemini CLI, Antigravity, and optionally Copilot Studio. Platform-specific documentation (config format, header requirements, endpoint URLs).

**Test plan:**
1. Gemini CLI — `gemini mcp add -t http --url http://127.0.0.1:8000/mcp`, call extract_structure_compact, verify response
2. Antigravity — `.gemini/antigravity/mcp_config.json` config, test MCP onboarding flow, verify tool execution
3. Copilot Studio (optional, deferred) — requires enterprise credentials, separate milestone

**Addresses:**
- Gemini CLI compatibility (Accept header handling, header configuration)
- Antigravity compatibility (config installation flow, `serverUrl` vs `url` parameter)

**Avoids:**
- Assuming same behavior as Claude Code (test explicitly with each platform)
- Missing Accept header (already handled in Phase 2, validated here)

### Phase Ordering Rationale

- **Phase 1 before Phase 2** — Must establish dual-transport foundation before adding protocol compliance. Changing transport mechanism after protocol layer is in place creates integration complexity.
- **Phase 2 before Phase 3** — Can't test HTTP protocol compliance until protocol layer exists. Tests verify implementation correctness.
- **Phase 3 before Phase 4** — Must prove server works correctly in isolation before testing with external clients. Integration tests catch server-side issues, cross-platform tests catch client-side issues.
- **No Phase 5 (deployment/production)** — Research confirms localhost-only v1 needs no authentication, rate limiting, or TLS. Defer to future enterprise deployment milestone.

**Grouping rationale from architecture research:**
- Phases 1-2 are single-developer work (code changes only, no external dependencies)
- Phase 3 requires test infrastructure setup but no external services
- Phase 4 requires external platform accounts (Gemini CLI, Antigravity) but no code changes

**Pitfall avoidance mapped to phases:**
- Phase 1: stdout pollution, session confusion, hardcoded config
- Phase 2: Accept header 406, protocol version mismatch, base64 encoding
- Phase 3: happy path testing trap
- Phase 4: client compatibility assumptions

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Cross-Platform Testing)** — Gemini CLI and Antigravity integration patterns are documented but not firsthand-tested. May encounter undocumented quirks. Medium research effort (1-2 hours) to verify config format and header requirements with actual platform instances.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Transport Setup)** — FastMCP flag-based transport selection is well-documented with multiple examples. Standard pattern, no research needed.
- **Phase 2 (Protocol Implementation)** — MCP protocol spec is canonical, header validation patterns are standard Starlette middleware. Implementation is straightforward.
- **Phase 3 (HTTP Integration Testing)** — FastMCP test utilities are documented, pytest patterns for HTTP server testing are standard. No novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All dependencies already installed and verified in requirements.txt. Versions match MCP SDK requirements exactly. FastMCP HTTP support is documented and battle-tested. |
| Features | HIGH | MCP spec is canonical for table stakes. Differentiators (transport parity, stateless design) align with existing architecture. Anti-features (session management, auth for v1) supported by security best practices for localhost-only deployment. |
| Architecture | HIGH | Single entry point with flag-based transport selection is the standard pattern documented in FastMCP, Microsoft, and multiple production examples. Existing project already follows transport-agnostic design (handlers have no MCP dependencies). |
| Pitfalls | HIGH | All 7 critical pitfalls sourced from production postmortems, GitHub issues, and official MCP documentation. stdout pollution, Accept header 406, and test coverage gaps are the most common failure modes documented across multiple sources. |

**Overall confidence:** HIGH

### Gaps to Address

Minor gaps that need validation during implementation:

- **Chromebook Crostini networking** — Research shows `127.0.0.1` binding prevents ChromeOS browser access to Crostini-hosted servers. Solution is binding to `0.0.0.0` or using `penguin.linux.test` domain with port forwarding enabled in ChromeOS settings. This is documented in ChromeOS.dev guides but not tested firsthand. **Validation:** During Phase 1, test HTTP server access from ChromeOS browser after deployment. If `127.0.0.1` doesn't work, switch to `0.0.0.0` with explicit Origin validation.

- **FastMCP session manager behavior** — Research indicates FastMCP provides StreamableHTTPSessionManager but unclear if it's enabled by default or requires explicit configuration. MCP SDK docs show `stateless=True` parameter but FastMCP wrapper may differ. **Validation:** During Phase 1, inspect FastMCP source or run initial HTTP server with verbose logging to confirm session ID behavior. If session IDs appear in responses, explicitly set `stateless=True`.

- **Accept header strictness in FastMCP** — Research shows MCP SDK rejects wildcard Accept headers by default, but unclear if FastMCP wrapper has relaxed validation. Some sources indicate FastMCP is more permissive for ease of local development. **Validation:** During Phase 2, test with curl sending `Accept: */*` and `Accept: application/json` only. If 406 errors occur, add custom middleware to accept wildcards.

All gaps are low-severity with documented workarounds. No gaps require fundamental architecture changes.

## Sources

### Primary (HIGH confidence)
- [FastMCP Running Your Server](https://gofastmcp.com/deployment/running-server) — transport parameter usage, CLI flags, official FastMCP docs
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) — official SDK repository, StreamableHTTPSessionManager implementation
- [MCP Transports Specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) — canonical transport protocol requirements
- [Microsoft Copilot Studio MCP Integration](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent) — Copilot Studio requirements, Streamable HTTP mandate
- requirements.txt (vibe-legal-form-filler) — verified installed dependencies match research recommendations

### Secondary (MEDIUM-HIGH confidence)
- [Dual-Transport MCP Servers: STDIO vs. HTTP Explained](https://medium.com/@kumaran.isk/dual-transport-mcp-servers-stdio-vs-http-explained-bd8865671e1f) — architectural patterns, rationale for dual transport
- [One MCP Server, Two Transports](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/one-mcp-server-two-transports-stdio-and-http/4443915) — Microsoft's guidance on dual-transport architecture
- [Implementing MCP: Tips, Tricks and Pitfalls](https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/) — production pitfalls, stdout pollution, session management
- [MCP Server Transports: STDIO, Streamable HTTP & SSE](https://docs.roocode.com/features/mcp/server-transports) — transport comparison, SSE deprecation timeline
- [Gemini CLI MCP Servers](https://geminicli.com/docs/tools/mcp-server/) — Gemini CLI integration patterns, header requirements
- [Antigravity MCP Integration](https://medium.com/@andrea.bresolin/using-an-mcp-server-with-google-antigravity-and-gemini-cli-for-android-development-efaea5a581ad) — Antigravity config format, compatibility notes

### Tertiary (MEDIUM confidence)
- [Stop Vibe-Testing Your MCP Server](https://www.jlowin.dev/blog/stop-vibe-testing-mcp-servers) — testing philosophy, HTTP integration test patterns
- [FastMCP Tests Documentation](https://gofastmcp.com/development/tests) — test utilities, StreamableHttpTransport usage
- [Port Forwarding | ChromeOS.dev](https://chromeos.dev/en/web-environment/port-forwarding) — Chromebook Crostini networking
- [MCP Base64 Encode/Decode Mismatch](https://github.com/modelcontextprotocol/python-sdk/issues/342) — GitHub issue documenting base64 encoding pitfall
- [MCP Server Won't Work with Wildcard Accept Header](https://github.com/modelcontextprotocol/python-sdk/issues/1641) — GitHub issue documenting Accept header strictness

---
*Research completed: 2026-02-16*
*Ready for roadmap: yes*
