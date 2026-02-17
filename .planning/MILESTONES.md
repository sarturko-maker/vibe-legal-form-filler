# Milestones

## v2.0: Performance Optimization

**Completed:** 2026-02-17
**Phases:** 5–6 (Phase 7 QA/Docs absorbed into v2.1)
**Requirements:** 7 (FAST-01–05, COMPAT-01–02)

**What shipped:**
- `answer_text` fast path: server builds insertion OOXML inline during write_answers
- Formatting inheritance identical to build_insertion_xml (font, size, bold, italic, color)
- All three insertion modes work with answer_text (replace_content, append, replace_placeholder)
- Multi-line answer_text with literal `\n` normalization and `<w:br/>` conversion
- Backward compatible: insertion_xml path unchanged, mixed mode supported
- 281 tests passing (47 new tests added)

**Key decisions:**
- Approach A (answer_text field) over batch tool or build_insertion_xml removal
- Empty strings treated as "not provided" for answer_text/insertion_xml
- Batch validation collects ALL errors before raising (no short-circuiting)

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
