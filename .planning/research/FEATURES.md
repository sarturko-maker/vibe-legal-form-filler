# Feature Landscape: MCP Round-Trip Reduction for Word Form Filling

**Domain:** MCP server performance optimization -- reducing tool call round-trips in agent pipelines
**Researched:** 2026-02-17
**Overall confidence:** HIGH

## The Problem

The current Word pipeline requires N+3 MCP tool calls for N answers:
- 1 call to `extract_structure_compact`
- 1 call to `validate_locations`
- N calls to `build_insertion_xml` (one per answer, to inherit formatting and build OOXML)
- 1 call to `write_answers` (batch write)
- 1 call to `verify_output`

For a 50-question form, that is 53 round-trips. Each round-trip costs: LLM inference latency (the agent must decide to call the tool), JSON serialization, MCP transport overhead, and context window consumption (every tool call + result lives in conversation history). Excel and PDF already skip `build_insertion_xml` entirely -- they pass plain values directly to `write_answers`. Only Word has this bottleneck because Word answers require format-inheriting OOXML.

## Table Stakes

Features that are required for the optimization to ship. Without these, the round-trip reduction is incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|-------------|------------|-------|
| **Plain-text fast path via `answer_text` field** | Agents already send plain text for Excel/PDF. Word should support the same. The server has the document bytes + XPath + target element -- everything needed to build OOXML internally. | Med | Add `answer_text: str = ""` to AnswerPayload. When present (and insertion_xml empty), server extracts formatting from target and builds the `<w:r>` XML inline during write_answers. |
| **Formatting inheritance from target element** | The whole point of build_insertion_xml is that answers inherit the target cell's font/size/bold/italic/color. The fast path must produce identical output. | Med | Reuse `_find_run_properties` and extract helpers from `xml_formatting.py` on live DOM elements. New function `extract_formatting_from_element()` avoids serialize-parse round trip. |
| **Backward compatibility with insertion_xml** | Existing agent workflows use insertion_xml exclusively. Breaking them = instant rollback. | Low | AnswerPayload keeps `insertion_xml: str = ""`. Both fields optional, exactly one must be non-empty. `insertion_xml` takes precedence if both provided. Old callers unchanged. |
| **All three insertion modes** | replace_content, append, replace_placeholder must all work with answer_text identically to insertion_xml. | Low | Fast path produces an insertion_xml string via build_run_xml(), then feeds it to the same mode handlers. No mode logic changes. |
| **Validation: either answer_text or insertion_xml required** | Agent sends neither -> clear error. Agent sends both -> insertion_xml wins (explicit XML is intentional). | Low | Validation in `_apply_answer()` and `_build_word_payloads()`. Rich error messages explain what to provide. |
| **Table cell wrapping (w:tc -> w:p -> w:r)** | When target is w:tc, bare w:r must be wrapped in w:p. | Low | Already handled in `_replace_content()`. Fast path produces the same w:r element, so existing wrapping works. |

## Differentiators

Features that provide additional value beyond the core round-trip reduction.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Mixed answer_text and insertion_xml in same call** | Agents migrate incrementally. Simple answers use answer_text, complex (structured) ones use insertion_xml, in the same write_answers call. | Low | `_apply_answer()` checks per-answer, not globally. Each answer takes its own code path. |
| **Parity guarantee (fast path == old path)** | A specific test proves fast path produces byte-identical output to build_insertion_xml + write_answers. Agents trust the optimization does not change results. | Med | Parity test runs both paths on same fixture, compares output bytes. |
| **Agent context reduction** | Agent no longer holds N target_context_xml strings (200-500 chars each) + N insertion_xml strings in context window. For 50 answers, saves ~30-50KB of context. | Low | Automatic consequence of eliminating build_insertion_xml calls. |
| **`extract_formatting_from_element()` public API** | Other internal code can extract formatting from live elements without serialize-parse overhead. Clean reusable function. | Low | Takes `etree._Element`, returns `dict`. Refactors existing `extract_formatting()` to call it internally. |

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Remove build_insertion_xml tool** | Breaking change. Agents using structured answer_type need it. Useful as debugging/inspection tool. | Keep it available. It handles structured (AI-generated OOXML) case which the fast path does not. |
| **New batch_build_insertion_xml tool** | Still requires an extra MCP round trip. Agent must still extract and pass target_context_xml for each answer. The fast path (inline in write_answers) eliminates the round trip entirely. | Use the answer_text fast path. For structured answers that truly need pre-built XML, the existing single build_insertion_xml tool suffices. |
| **Heuristic detection (sniff insertion_xml content)** | Checking if insertion_xml starts with `<w:` to detect pre-built XML vs plain text is fragile. Answers starting with `<` break the heuristic. Creates ambiguity. | Use explicit `answer_text` field. Unambiguous: presence of `answer_text` triggers fast path, presence of `insertion_xml` triggers old path. |
| **Async/parallel XML building** | CPU-bound lxml work (~0.86ms per SubElement tree). Python GIL prevents parallelism. Total time for 30 answers is ~26ms. Async adds complexity for zero speedup. | Keep synchronous loop. 26ms total is negligible vs MCP overhead. |
| **Template caching for formatting** | Each target element has different formatting. No cache hits. Cache invalidation adds complexity for no gain. | Extract formatting fresh per answer from the live tree. |
| **Multi-line answer_text handling** | Newlines create ambiguity (paragraph breaks vs literal?). Current build_insertion_xml does not handle this either. | Treat as single-run content. If agents need paragraph breaks, use insertion_xml with explicit w:p elements. |
| **Automatic answer_text for Excel/PDF** | Excel/PDF already accept plain text in insertion_xml field. Adding answer_text would be redundant. | Keep Excel/PDF using insertion_xml for plain values. answer_text is Word-specific. |
| **BatchIt-style meta-batching** | Wrapping arbitrary tool calls into one batch_execute envelope adds indirection, makes error handling opaque. | Make individual tools smart enough to handle batches natively. write_answers already accepts a list. |
| **write_and_verify combined tool** | Reduces one more round-trip but adds API surface. Can be added independently later. | Keep separate tools for now. Focus this milestone on the N-call bottleneck, not the 1-call optimization. |
| **Per-answer status reporting** | Adding answer_statuses array to write_answers response. Useful but separate concern. Current write_answers raises on first failure -- changing to partial-success is a behavior change. | Keep existing fail-fast behavior. Per-answer status is a separate milestone. |

## Feature Dependencies

```
extract_formatting_from_element() [xml_formatting.py]
    <- used by -> fast path in _apply_answer() [word_writer.py]
    <- also called by -> extract_formatting() [xml_formatting.py, refactored]

answer_text field [models.py]
    <- used by -> _apply_answer() fast path [word_writer.py]
    <- validated by -> _build_word_payloads() [tool_errors.py]

Fast path in _apply_answer() [word_writer.py]
    <- requires -> extract_formatting_from_element()
    <- requires -> build_run_xml() [already exists]
    <- requires -> answer_text field on AnswerPayload

Parity test [tests/]
    <- requires -> all of the above
    <- compares -> fast path output vs old path output
```

## MVP Recommendation

Prioritize:
1. **Formatting inheritance from live element** -- core value. Without this the optimization is useless.
2. **Backward compatibility** -- zero breaking changes. Old callers must work unchanged.
3. **Parity test** -- proves the optimization does not change document output.
4. **Mixed mode support** -- agents migrate incrementally.

Defer:
- **Per-answer status reporting**: Behavior change (fail-fast to partial-success). Separate milestone.
- **write_and_verify combo**: One fewer round-trip, but separate concern. Can add independently.
- **Formatting override hints**: Low demand. Most form answers inherit target formatting.
- **Unified answer schema across file types**: Larger refactor. Fast path already makes Word accept plain text.

## Impact Analysis

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| MCP calls for 50 answers | 53 | 4 | 92% fewer calls |
| Agent context for answers | ~50 insertion_xml + 50 target_context_xml strings | 50 answer_text strings | ~60% less context |
| Files changed | -- | 4 | Minimal surface area |
| Lines added | -- | ~45 | Small change |
| Breaking changes | -- | 0 | Full backward compat |
| New MCP tools | -- | 0 | No new API surface |

## Updated Pipeline (After Fast Path)

```
Current (Word): N + 4 calls
  1. extract_structure_compact  (1 call)
  2. validate_locations         (1 call)
  3. build_insertion_xml        (N calls -- THE BOTTLENECK)
  4. write_answers              (1 call)
  5. verify_output              (1 call)

After fast path (Word): 4 calls (constant)
  1. extract_structure_compact  (1 call)
  2. validate_locations         (1 call)
  3. write_answers              (1 call -- answer_text, server builds XML)
  4. verify_output              (1 call)
```

The Word pipeline matches Excel/PDF: 4 constant calls regardless of answer count.

## Sources

- Direct codebase analysis of `src/xml_formatting.py`, `src/handlers/word_writer.py`, `src/models.py`, `src/tool_errors.py` (HIGH confidence)
- [lxml Performance Benchmarks](https://lxml.de/performance.html) -- SubElement ~0.86ms, confirms CPU time is negligible (HIGH confidence)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- no native batch tool protocol (HIGH confidence)
- [mcp-batchit](https://github.com/ryanjoachim/mcp-batchit) -- external proxy pattern, validates no native batch exists (MEDIUM confidence)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) -- v1.26.0, FastMCP integrated (HIGH confidence)

---
*Feature research for: MCP form-filler round-trip reduction*
*Researched: 2026-02-17*
