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

## v2.1: Gemini Consolidation

**Completed:** 2026-02-17
**Phases:** 8–11
**Requirements:** 17 (ERG-01–05, TOL-01–02, VER-01–02, PIPE-01–04, QA-01–04)

**What shipped:**
- pair_id→xpath resolution: agents send pair_id + answer_text only, server resolves xpath and mode
- SKIP convention for intentionally blank fields (signatures, dates) with summary counts
- file_path echo in extract_structure_compact and improved error messages
- Cross-check validation when both xpath and pair_id provided (pair_id wins)
- verify_output accepts pair_id without xpath, matching write_answers capability
- 7-step CLAUDE.md pipeline with simplified fast-path agent guidance
- 311 tests passing (30 new tests for v2.1 features)

**Key decisions:**
- Stateless pair_id resolution via re-extraction (small perf cost, eliminates agent bookkeeping)
- Relaxed path for Excel/PDF uses pair_id as xpath directly (no re-extraction)
- Cross-check warnings only on Word path (where xpath and pair_id are distinct systems)
- Dict injection after model_dump() for response augmentation (avoids Pydantic model changes)
- SKIP filtering at tools_write.py level after validation (keeps routing separate)

---

