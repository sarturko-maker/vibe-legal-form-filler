# Phase 1: Transport Setup - Context

**Gathered:** 2026-02-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Add HTTP transport mode alongside existing stdio so the server can be started in either mode via a runtime flag. All 6 MCP tools and utilities must be available identically in both transports. No protocol compliance (headers, error codes) — that's Phase 2.

</domain>

<decisions>
## Implementation Decisions

### CLI flag design
- Use `--transport {stdio,http}` (choices) instead of a boolean `--http` flag — more extensible
- Default is `stdio` — shown explicitly in `--help` output
- Add `--port` flag (default 8000) for HTTP transport
- Add `--host` flag (default 127.0.0.1) for HTTP transport
- `--port` and `--host` error and exit if used without `--transport http` — no silent ignore
- argparse handles both `--transport=http` and `--transport http` (native behavior)
- `--help` includes usage examples in epilog (e.g., `mcp-form-filler --transport http --port 9000`)
- Port validated to range 1024-65535 — reject privileged and invalid ports with clear error
- Environment variable fallbacks: `MCP_FORM_FILLER_TRANSPORT`, `MCP_FORM_FILLER_PORT`, `MCP_FORM_FILLER_HOST` — CLI flags take precedence
- Use argparse (stdlib) — no additional CLI dependencies

### Entry point
- Both `python -m src.server` and named script `mcp-form-filler` work
- Add `console_scripts` entry in pyproject.toml for `mcp-form-filler`
- server.py remains the entry point — CLI parsing and transport dispatch stay there

### Port conflict handling
- If port is in use: print `Error: Port 8000 is already in use. Try: --port 8001` and exit non-zero
- No auto-increment, no process info lookup — simple clear message with suggestion
- Graceful shutdown on Ctrl+C — finish in-flight requests (with timeout), then exit cleanly

### Code organization
- HTTP transport logic in a single file: `src/http_transport.py`
- Strict 200-line file limit applies — split if it exceeds
- Use FastMCP's built-in streamable HTTP support (`mcp.run(transport='streamable-http')`) — minimal custom code
- server.py handles CLI parsing and dispatches to either stdio or HTTP startup path

### Claude's Discretion
- Exact argparse group/subcommand structure
- Graceful shutdown timeout duration
- How FastMCP's built-in HTTP is configured (if it needs ASGI middleware, etc.)
- Error message formatting details

</decisions>

<specifics>
## Specific Ideas

- CLI should feel like standard Python tooling — argparse, `--help` with examples, env var fallbacks
- Entry point name `mcp-form-filler` aligns with MCP ecosystem naming conventions
- Error-on-misuse for HTTP-only flags prevents confusion when agents pass wrong flag combinations

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-transport-setup*
*Context gathered: 2026-02-16*
