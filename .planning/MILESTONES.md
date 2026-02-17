# Milestones

## v1.0: Cross-Platform Transport & Enterprise Integration

**Completed:** 2026-02-17
**Phases:** 1–4
**Requirements:** 20 (TRANS-01–07, TEST-01–05, XPLAT-01–04, DOCS-01–04)

**What shipped:**
- Streamable HTTP transport via `--http` flag (stdio preserved as default)
- Full MCP protocol compliance (header validation, JSON-RPC errors, origin checks)
- HTTP integration test suite (transport parity, concurrency, error coverage)
- Setup documentation for Claude Code, Gemini CLI, Antigravity
- 234 tests passing across all formats and transports
- Rich MCP tool validation error messages (tool_errors.py)

**Key decisions:**
- Built-in transport flag over separate wrapper process
- Localhost-only binding for HTTP (no auth needed for v1)
- Copilot Studio deferred (enterprise credentials not available)
- Custom uvicorn runner for port pre-check and graceful shutdown
