# Vibe Legal Form Filler — Cross-Platform Transport & Enterprise Integration

## What This Is

An MCP server (Python, FastMCP) that provides deterministic form-filling tools for AI agents — extracting structure from Word/Excel/PDF documents, validating answer locations, writing answers, and verifying output. Currently works over stdio transport with Claude Code. This milestone adds Streamable HTTP transport so the server can be reached by HTTP-based platforms like Microsoft Copilot Studio, while keeping stdio working for existing clients.

## Core Value

The server must work identically over both stdio and HTTP transports — same tools, same inputs, same outputs, no behavioral differences. An agent shouldn't know or care which transport it's using.

## Requirements

### Validated

- ✓ Extract compact structure from Word (.docx) with stable element IDs — existing
- ✓ Extract compact structure from Excel (.xlsx) with S-R-C IDs — existing
- ✓ Extract compact structure from PDF (AcroForm) with sequential F-IDs — existing
- ✓ Validate answer locations across all three formats — existing
- ✓ Build insertion XML for Word answers with formatting inheritance — existing
- ✓ Write answers to Word/Excel/PDF documents — existing
- ✓ Verify output correctness and structural integrity — existing
- ✓ Stateless MCP server over stdio transport (FastMCP) — existing
- ✓ 172 unit tests passing across all formats — existing
- ✓ Modular codebase (no file over 200 lines) — existing

### Active

- [ ] Add Streamable HTTP transport as built-in mode (flag to choose stdio vs HTTP)
- [ ] Keep stdio transport working exactly as it does now
- [ ] All 6 MCP tools work identically over both transports
- [ ] Integration tests confirming transport parity (same tool, same input, same output over stdio and HTTP)
- [ ] Cross-platform test: Gemini CLI completes full questionnaire pipeline
- [ ] Cross-platform test: Antigravity completes full questionnaire pipeline
- [ ] Setup documentation for each tested platform (Claude Code, Gemini CLI, Antigravity)
- [ ] All 172 existing tests still pass after transport changes

### Out of Scope

- API key authentication — v2 requirement for enterprise deployment behind corporate networks
- Microsoft Copilot Studio connection — requires enterprise credentials and network access not available on personal Chromebook; separate follow-up milestone
- Node.js rewrite — Python only
- Docker containerization — runs locally on Chromebook
- Web UI or REST API — MCP protocol only
- Any changes to core document processing logic

## Context

- The server is already complete and working over stdio. All 6 MCP tools (extract_structure_compact, extract_structure, validate_locations, build_insertion_xml, write_answers, verify_output) plus utilities (extract_text, list_form_fields) are production-ready.
- Microsoft Copilot Studio now supports MCP servers natively via Streamable HTTP transport — this is the primary motivation for adding HTTP.
- The MCP Python SDK (FastMCP) likely already supports Streamable HTTP transport as a built-in option. Research needed to confirm API and configuration.
- The server is stateless — each tool call is independent. This makes transport-layer changes clean since there's no session state to manage.
- Gemini CLI and Antigravity are realistic cross-platform test targets available on a Chromebook.
- The orchestration pipeline is agent-driven: extract → validate → build XML → write → verify. The MCP server provides tools; the agent drives the workflow.

## Constraints

- **Language**: Python only — no Node.js, no TypeScript
- **License**: AGPL-3.0, open source
- **Test regression**: All 172 existing tests must pass after every change
- **File size**: No file over 200 lines (vibe coding maintenance principle)
- **Platform**: Runs locally on a Chromebook with Linux (Crostini)
- **Transport**: HTTP binds to localhost only (no auth needed for v1)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Built-in transport mode (flag) over separate wrapper process | Simpler deployment, single process, no IPC complexity | — Pending |
| Localhost-only binding for HTTP | Personal Chromebook use, no auth needed for v1 | — Pending |
| Copilot Studio deferred to separate milestone | Requires enterprise credentials not available on personal device | — Pending |

---
*Last updated: 2026-02-16 after initialization*
