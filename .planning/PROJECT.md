# Vibe Legal Form Filler

## What This Is

An MCP server (Python, FastMCP) that provides deterministic form-filling tools for AI agents — extracting structure from Word/Excel/PDF documents, validating answer locations, writing answers, and verifying output. Works over both stdio and Streamable HTTP transports. Used by Claude Code, Gemini CLI, and Antigravity.

## Core Value

Agents fill forms correctly and fast — the server handles all deterministic document manipulation so agents never touch raw OOXML, and the pipeline completes in the fewest possible round-trips.

## Latest Milestone: v2.1 Gemini Consolidation (shipped 2026-02-17)

Delivered zero-friction fast path: agents send pair_id + answer_text only, server resolves xpath and mode automatically. SKIP convention for intentionally blank fields. 311 tests passing.

## Requirements

### Validated

- ✓ Extract compact structure from Word (.docx) with stable element IDs — v1.0
- ✓ Extract compact structure from Excel (.xlsx) with S-R-C IDs — v1.0
- ✓ Extract compact structure from PDF (AcroForm) with sequential F-IDs — v1.0
- ✓ Validate answer locations across all three formats — v1.0
- ✓ Build insertion XML for Word answers with formatting inheritance — v1.0
- ✓ Write answers to Word/Excel/PDF documents — v1.0
- ✓ Verify output correctness and structural integrity — v1.0
- ✓ Stateless MCP server over stdio transport (FastMCP) — v1.0
- ✓ Streamable HTTP transport via --http flag — v1.0
- ✓ MCP protocol compliance (headers, errors, version negotiation) — v1.0
- ✓ Transport parity (identical behavior over stdio and HTTP) — v1.0
- ✓ Cross-platform verified (Gemini CLI, Antigravity) — v1.0
- ✓ Rich tool validation error messages for agent self-correction — v1.0
- ✓ 234 tests passing across all formats and transports — v1.0
- ✓ Modular codebase (no file over 200 lines) — v1.0
- ✓ Fast path: server builds OOXML from answer_text, eliminating build_insertion_xml round-trips — v2.0
- ✓ Formatting inheritance identical to build_insertion_xml — v2.0
- ✓ All three insertion modes work with answer_text — v2.0
- ✓ Multi-line answer_text converts to `<w:br/>` elements (real and literal \n) — v2.0
- ✓ Backward-compatible: insertion_xml path unchanged, mixed mode supported — v2.0
- ✓ 281 tests passing after v2.0 — v2.0
- ✓ pair_id→xpath resolution in write_answers and verify_output — v2.1
- ✓ mode defaults to replace_content when answer_text provided — v2.1
- ✓ SKIP convention for intentionally blank fields — v2.1
- ✓ verify_output accepts pair_id without xpath — v2.1
- ✓ extract_structure_compact echoes file_path in response — v2.1
- ✓ Improved error messages referencing extract_structure_compact — v2.1
- ✓ Style review step in CLAUDE.md pipeline — v2.1
- ✓ 311 tests passing after v2.1 — v2.1

### Active

(No active requirements — next milestone TBD)

### Out of Scope

- API key authentication — separate enterprise milestone
- Microsoft Copilot Studio connection — requires enterprise credentials
- Node.js rewrite — Python only
- Docker containerization — runs locally on Chromebook
- Web UI or REST API — MCP protocol only
- Changes to extract_structure or validate_locations (read-side tools are not the bottleneck)
- Async/streaming within a single tool call — MCP tools are synchronous request/response

## Context

- Three milestones shipped: v1.0 (transports), v2.0 (fast path), v2.1 (ergonomics)
- 311 tests across Word, Excel, PDF, HTTP transport, resolution, ergonomics
- Codebase: ~4,500 LOC Python (src/), ~3,000 LOC tests
- Agents can now fill a 30-question Word form with pair_id + answer_text only — no xpath, no mode, no build_insertion_xml calls
- All three platforms verified: Claude Code (stdio), Gemini CLI (HTTP), Antigravity (HTTP)

## Constraints

- **Language**: Python only
- **License**: AGPL-3.0, open source
- **Test regression**: All 311 tests must pass after every change
- **File size**: No file over 200 lines
- **Backward compatibility**: Existing agents using the current pipeline must not break
- **Platform**: Runs locally on a Chromebook with Linux (Crostini)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Built-in transport mode (flag) over separate wrapper process | Simpler deployment, single process, no IPC complexity | ✓ Good |
| Localhost-only binding for HTTP | Personal Chromebook use, no auth needed for v1 | ✓ Good |
| Copilot Studio deferred to separate milestone | Requires enterprise credentials not available on personal device | ✓ Good |
| Custom uvicorn runner for HTTP | Port pre-check and graceful shutdown timeout | ✓ Good |
| Research round-trip reduction before committing to approach | Multiple valid strategies; trade-offs need evaluation | ✓ Good |
| answer_text fast path (Approach A) over batch tool or removal | Simplest API change, backward compatible, no extra round-trips | ✓ Good |
| Stateless pair_id resolution via re-extraction | Small perf cost but eliminates agent xpath bookkeeping | ✓ Good |
| Relaxed path for Excel/PDF uses pair_id as xpath directly | No re-extraction needed, pair_id IS the element ID | ✓ Good |
| Cross-check warnings only on Word path | Excel/PDF pair_id and xpath are the same identifier | ✓ Good |
| Dict injection after model_dump() for response augmentation | Avoids modifying Pydantic models for echo/metadata fields | ✓ Good |
| SKIP filtering at tools_write.py level (not handler) | Keeps validation and routing separate | ✓ Good |

---
*Last updated: 2026-02-17 after v2.1 milestone*
