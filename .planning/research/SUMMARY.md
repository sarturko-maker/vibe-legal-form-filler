# Project Research Summary

**Project:** Form Filler MCP Server -- v2.0 Round-Trip Reduction
**Domain:** MCP server performance optimization (OOXML batch processing)
**Researched:** 2026-02-17
**Confidence:** HIGH

## Executive Summary

The Word form-filling pipeline has a structural bottleneck: for every answer, the agent must make a separate MCP call to `build_insertion_xml` to convert plain text into format-inheriting OOXML. A 50-question form requires 53 round-trips (N+3). Each round-trip costs LLM inference latency, JSON serialization overhead, and context window consumption. Excel and PDF already skip this step entirely -- only Word has the problem because Word answers require OOXML with inherited formatting. The fix is straightforward: no new dependencies, no new tools, no protocol changes.

The recommended approach (Approach A) adds an optional `answer_text` field to `AnswerPayload`. When `write_answers` receives `answer_text` instead of `insertion_xml`, the server extracts formatting from the target element's live DOM and builds the run XML inline -- the same logic that `build_insertion_xml` performs, but without the serialize-parse-serialize overhead and without the MCP round-trip. This reduces the pipeline from N+3 calls to a constant 4 calls regardless of answer count, a 92% reduction for a 50-question form. The change touches 4 files and adds roughly 45 lines.

The primary risks are formatting parity (the fast path must produce identical output to the old path) and edge-case text handling (newlines, tabs, leading/trailing spaces). Both are mitigated by comparison tests that run both paths on the same fixture data. The existing `build_insertion_xml` tool remains available for structured answers and backward compatibility -- this is an additive optimization, not a replacement.

## Key Findings

### Recommended Stack

No new dependencies. The current stack (lxml 6.0.2, MCP SDK 1.26.0, pydantic 2.12.5) already contains everything needed. The bottleneck is protocol-level overhead (30 sequential MCP round-trips at 100-200ms each), not library performance (lxml builds 30 runs in ~26ms total).

**Core technologies (unchanged):**
- **lxml 6.0.2**: OOXML tree manipulation -- SubElement-based run building, direct element access eliminates serialize/parse overhead
- **MCP SDK 1.26.0**: FastMCP framework -- no native batch tool protocol exists in MCP spec; server-side batching via combined tools is the standard pattern
- **pydantic 2.12.5**: Input validation -- optional field with default handles backward compatibility natively

### Expected Features

**Must have (table stakes):**
- Plain-text fast path via `answer_text` field on `AnswerPayload`
- Formatting inheritance from target element (identical to `build_insertion_xml` output)
- Full backward compatibility with `insertion_xml` (zero breaking changes)
- All three insertion modes (replace_content, append, replace_placeholder) work with `answer_text`
- Validation: exactly one of `answer_text` or `insertion_xml` must be non-empty

**Should have (differentiators):**
- Mixed `answer_text` and `insertion_xml` in the same `write_answers` call (incremental migration)
- Parity test proving fast path produces byte-identical output to old path
- `extract_formatting_from_element()` as a public API in `xml_formatting.py`

**Defer (v2+):**
- Per-answer status reporting (changes fail-fast behavior -- separate concern)
- `write_and_verify` combined tool (saves 1 more round-trip, independent optimization)
- Multi-line `answer_text` handling with `<w:br/>` elements (scope creep risk)
- Formatting override hints (low demand)

### Architecture Approach

Approach A (fast path in `write_answers`) wins over two alternatives. Approach B (batch `build_insertion_xml` tool) still requires an extra round-trip and agent-side `target_context_xml`. Approach C (remove `build_insertion_xml`) is a breaking change that loses structured XML support. Approach A delivers zero extra round-trips for plain text, full backward compatibility, and no new API surface.

**Files that change:**
1. **`src/xml_formatting.py`** (~10 lines) -- add `extract_formatting_from_element()` public function
2. **`src/models.py`** (~4 lines) -- add optional `answer_text: str = ""` to `AnswerPayload`
3. **`src/handlers/word_writer.py`** (~25 lines) -- add fast path in `_apply_answer()`, new `_build_insertion_xml_from_target()` helper
4. **`src/tool_errors.py`** (~8 lines) -- update validation to accept `answer_text` as alternative to `insertion_xml`

**Files that do NOT change:** `tools_write.py`, `tools_extract.py`, `mcp_app.py`, `word_parser.py`, `word_indexer.py`, all Excel/PDF handlers.

### Critical Pitfalls

1. **Formatting extraction divergence** -- fast path must use the exact same `_find_run_properties()` logic. Do NOT walk up the element tree to resolve OOXML's 5-level style hierarchy. Mitigate with comparison test (both paths, same fixture, identical output).

2. **Structured answers cannot use fast path** -- `answer_type="structured"` requires agent-provided OOXML. Fast path handles `plain_text` only. Validate and reject structured answers in fast path with clear error.

3. **Multi-run formatting ambiguity** -- `_find_run_properties()` picks the first run, but labels are often bold while placeholders are not. Accept this as a known limitation (same behavior as current path). Document the heuristic.

4. **xml:space="preserve" edge cases** -- `build_run_xml()` handles leading/trailing spaces but not embedded newlines or tabs. Add test coverage for edge-case text before shipping.

5. **Partial batch failure** -- if answer 25/50 fails after 1-24 are applied, all work is lost. Mitigate with validate-all-before-apply-any pattern inside the write loop.

## Implications for Roadmap

Based on combined research, this is a small, well-scoped refactoring. The suggested phases below can be collapsed into fewer phases if the roadmapper prefers -- total production code is ~45 lines.

### Phase 1: Formatting Extraction (Foundation)
**Rationale:** All other changes depend on extracting formatting from live DOM elements. Independently testable.
**Delivers:** `extract_formatting_from_element()` in `xml_formatting.py`; refactored `extract_formatting()` to call it internally.
**Addresses:** Core formatting inheritance, `extract_formatting_from_element()` public API (differentiator).
**Avoids:** Formatting divergence pitfall -- same `_find_run_properties()` logic, different entry point.

### Phase 2: Model and Validation (API Contract)
**Rationale:** Can proceed in parallel with Phase 1. Defines the contract before implementation.
**Delivers:** `answer_text` field on `AnswerPayload`, updated validation in `tool_errors.py`.
**Addresses:** Backward compatibility, input validation, clear error messages.
**Avoids:** Structured answer conflation -- validation explicitly rejects ambiguous inputs.

### Phase 3: Fast Path Implementation (Core Logic)
**Rationale:** Depends on Phases 1 and 2. This is the actual round-trip elimination.
**Delivers:** `_build_insertion_xml_from_target()` and modified `_apply_answer()` in `word_writer.py`.
**Addresses:** The N-call bottleneck. Pipeline drops from N+3 to 4 constant calls.
**Avoids:** Double parsing (single-parse architecture), partial failure (validate-then-apply).

### Phase 4: Parity Tests and Documentation
**Rationale:** Proves the optimization is correct. Updates agent guidance in CLAUDE.md.
**Delivers:** 9 new test cases (including parity test), updated pipeline description and agent instructions.
**Addresses:** Parity guarantee, agent migration path, mixed-mode support verification.
**Avoids:** Silent formatting differences between paths, agent confusion about when to use which path.

### Phase Ordering Rationale

- Phases 1 and 2 are independent and can be built in parallel
- Phase 3 depends on both 1 and 2 (needs the function and the model field)
- Phase 4 must come last (tests and documents the integrated feature)
- Total scope is small (~45 lines of production code) -- the roadmapper should consider collapsing into 2-3 phases

### Research Flags

Phases with standard patterns (skip research-phase):
- **All phases:** This is an internal refactoring of existing code with no external dependencies, no new libraries, and no novel patterns. Every file change is mapped to specific line numbers in the codebase. No phase needs additional research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct inspection of installed packages and codebase confirms no additions needed. lxml benchmarks from official docs confirm performance. |
| Features | HIGH | Feature set narrowly scoped: one new optional field, one new internal function, one modified code path. No ambiguity about what to build. |
| Architecture | HIGH | Direct code analysis of all affected files. Import dependencies verified. Backward compatibility confirmed by model default values. Three approaches compared with clear winner. |
| Pitfalls | HIGH | Main risk (formatting parity) is verifiable with a deterministic test. All pitfalls mapped to specific code locations with concrete prevention strategies. |

**Overall confidence:** HIGH

### Gaps to Address

- **Multi-run formatting heuristic**: Current first-run-wins behavior may produce wrong formatting for cells with bold labels + normal placeholders. Not a blocker -- same behavior as current path -- but worth a follow-up investigation after v2.0 ships.
- **Newline/tab handling in `answer_text`**: Research identified edge cases but recommends deferring multi-line support to avoid scope creep. If agents send newlines, fast path should either strip them or raise a clear error. Design decision needed during Phase 3.
- **Agent behavior change**: The calling agent needs updated guidance. CLAUDE.md must clearly state `answer_text` is the preferred path for plain text answers.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis: `src/xml_formatting.py`, `src/handlers/word_writer.py`, `src/models.py`, `src/tool_errors.py`, `src/tools_extract.py`
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- no native batch tool protocol
- [lxml Performance Benchmarks](https://lxml.de/performance.html) -- SubElement ~0.86ms/pass
- [MCP Python SDK v1.26.0](https://github.com/modelcontextprotocol/python-sdk) -- FastMCP integrated, no batch API

### Secondary (MEDIUM confidence)
- [OOXML Style Hierarchy](https://c-rex.net/samples/ooxml/e1/Part4/OOXML_P4_DOCX_Style_topic_ID0ECYKT.html) -- formatting inheritance rules
- [OOXML rPr Specification](https://c-rex.net/samples/ooxml/e1/part4/OOXML_P4_DOCX_rPr_topic_ID0EEHTO.html) -- run properties element definition
- [mcp-batchit](https://github.com/ryanjoachim/mcp-batchit) -- validates no native MCP batch mechanism exists
- [Google AIP-180](https://google.aip.dev/180) -- backward compatibility principles

---
*Research completed: 2026-02-17*
*Ready for roadmap: yes*
