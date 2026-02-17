# Vibe Legal Form Filler

## What This Is

An MCP server (Python, FastMCP) that provides deterministic form-filling tools for AI agents — extracting structure from Word/Excel/PDF documents, validating answer locations, writing answers, and verifying output. Works over both stdio and Streamable HTTP transports. Used by Claude Code, Gemini CLI, and Antigravity.

## Core Value

Agents fill forms correctly and fast — the server handles all deterministic document manipulation so agents never touch raw OOXML, and the pipeline completes in the fewest possible round-trips.

## Current Milestone: v2.0 Performance Optimization

**Goal:** Reduce MCP round-trips so a 30-question questionnaire completes in minutes, not 10+, by eliminating the per-answer build_insertion_xml bottleneck.

**Target features:**
- Batch or inline XML generation to eliminate per-answer round-trips
- Backward-compatible API (existing agents keep working)
- Performance benchmarking to measure improvement

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

### Active

- [ ] Reduce round-trips for the build_insertion_xml → write_answers bottleneck
- [ ] Agents can fill a 30-question Word form without calling build_insertion_xml per answer
- [ ] Backward compatibility: existing agents using the current 5-step pipeline keep working
- [ ] Performance benchmarking showing measurable improvement in total pipeline time
- [ ] All 234 existing tests still pass after changes

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
- **Test regression**: All 234 existing tests must pass after every change
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
| Research round-trip reduction before committing to approach | Multiple valid strategies; trade-offs need evaluation | — Pending |

---
*Last updated: 2026-02-17 after milestone v2.0 initialization*
