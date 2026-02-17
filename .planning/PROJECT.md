# Vibe Legal Form Filler

## What This Is

An MCP server (Python, FastMCP) that provides deterministic form-filling tools for AI agents — extracting structure from Word/Excel/PDF documents, validating answer locations, writing answers, and verifying output. Works over both stdio and Streamable HTTP transports. Used by Claude Code, Gemini CLI, and Antigravity.

## Core Value

Agents fill forms correctly and fast — the server handles all deterministic document manipulation so agents never touch raw OOXML, and the pipeline completes in the fewest possible round-trips.

## Current Milestone: v2.1 Gemini Consolidation

**Goal:** Fix cross-platform agent ergonomics issues discovered during Gemini CLI testing — make the fast path truly zero-friction by resolving xpaths from pair_ids, defaulting modes, handling skips, and updating pipeline guidance.

**Target features:**
- pair_id→xpath resolution in write_answers and verify_output (agents don't need to carry xpaths)
- SKIP convention for intentionally blank fields (signatures, dates)
- file_path echo in extract_structure_compact response
- Style review step in CLAUDE.md pipeline guidance
- Updated tool docstrings and error messages

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

### Active

- [ ] pair_id→xpath resolution in write_answers (no xpath needed with answer_text)
- [ ] mode defaults to replace_content when answer_text provided
- [ ] SKIP convention for intentionally blank fields
- [ ] verify_output accepts pair_id without xpath
- [ ] extract_structure_compact echoes file_path in response
- [ ] Improved error messages referencing extract_structure_compact
- [ ] Style review step in CLAUDE.md pipeline
- [ ] All 281 existing tests pass after changes

### Out of Scope

- API key authentication — separate enterprise milestone
- Microsoft Copilot Studio connection — requires enterprise credentials
- Node.js rewrite — Python only
- Docker containerization — runs locally on Chromebook
- Web UI or REST API — MCP protocol only
- Changes to extract_structure or validate_locations (read-side tools are not the bottleneck)
- Async/streaming within a single tool call — MCP tools are synchronous request/response

## Context

- The Gemini CLI cross-platform test proved the server works but a 30-question questionnaire takes 10+ minutes. The bottleneck is 30 individual build_insertion_xml calls before write_answers.
- Excel and PDF paths are already fast — they skip build_insertion_xml entirely (plain values, not OOXML). Only Word has the bottleneck.
- build_insertion_xml does two things: (1) extract formatting from target XML context, (2) wrap answer text in a `<w:r>` with inherited formatting. For plain_text answers (the common case), this is deterministic and could be done server-side during write.
- The server already has all the XML utilities needed (xml_formatting.py, xml_formatting.py) — the question is where in the pipeline to invoke them.
- Agents currently send target_context_xml to build_insertion_xml — this is XML they got from extract_structure (raw mode) or that the server could look up from the XPath during write.

## Constraints

- **Language**: Python only
- **License**: AGPL-3.0, open source
- **Test regression**: All 281 existing tests must pass after every change
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
| Stateless pair_id resolution via re-extraction | Small perf cost but eliminates agent xpath bookkeeping | — Pending |

---
*Last updated: 2026-02-17 after milestone v2.1 initialization*
