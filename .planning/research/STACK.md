# Stack Research: Batch XML Generation for MCP Round-Trip Reduction

**Domain:** MCP server performance optimization (OOXML batch processing)
**Researched:** 2026-02-17
**Overall Confidence:** HIGH

## Executive Summary

No new dependencies are needed. The round-trip reduction is an architectural refactoring of existing code, not a technology addition. The current stack (lxml 6.0.2, MCP SDK 1.26.0, Python 3.11+) already contains every capability required. The bottleneck is not library performance -- it is protocol-level overhead from 30 sequential agent-to-server round trips. The fix is moving formatting extraction into `write_answers` so the agent sends plain text instead of pre-built XML.

## What Changes (and What Does Not)

### No New Dependencies

| Current Technology | Version | Role in Fix | Change Needed |
|-------------------|---------|-------------|---------------|
| lxml | 6.0.2 | XML formatting extraction + run building | Move existing logic into write_answers path |
| MCP SDK (mcp) | 1.26.0 | Tool registration and dispatch | No change to SDK usage |
| pydantic | 2.12.5 | Input models for the new answer format | Add optional fields to existing models |
| python-docx | 1.2.0 | Not involved (lxml handles OOXML directly) | No change |

### Core Approach: Inline Formatting in write_answers

The existing `build_insertion_xml` tool does two things per call:
1. `extract_formatting(target_context_xml)` -- parses target element XML, extracts font/size/bold/italic/underline/color
2. `build_run_xml(answer_text, formatting)` -- creates a `<w:r>` element with that formatting

Both functions live in `xml_formatting.py` (lines 124-197). They are pure functions with no state. The fix is to call these same functions inside `word_writer.py` during `write_answers`, eliminating the need for the agent to call `build_insertion_xml` 30 times.

## Recommended Stack (Unchanged)

### Core Technologies

| Technology | Version | Purpose | Why It Already Suffices |
|------------|---------|---------|------------------------|
| lxml | 6.0.2 | OOXML tree manipulation | SubElement-based `build_run_xml` creates one `<w:r>` per answer (~0.86ms). For 30 answers that is ~26ms total -- negligible. The bottleneck is 30 MCP round trips (100-200ms each), not lxml tree-building speed. |
| MCP SDK (mcp) | 1.26.0 | FastMCP server framework | Built-in `@mcp.tool()` decorator. No batch tool protocol exists in MCP spec 2025-11-25 -- the spec supports JSON-RPC batching but client implementations (Claude, Cursor, etc.) make sequential `tools/call` requests. Server-side batching via combined tools is the standard pattern. |
| pydantic | 2.12.5 | Tool input/output validation | Models like `AnswerPayload` need one optional field added (`answer_text`). Pydantic handles optional fields and backward compatibility natively. |

### Supporting Libraries (No Additions)

| Library | Version | Role | Change Needed |
|---------|---------|------|---------------|
| xml_formatting.py | internal | `extract_formatting()` and `build_run_xml()` | Already importable from `src.xml_formatting`. Import into `word_writer.py`. |
| xml_validation.py | internal | `is_well_formed_ooxml()` | Still needed for `structured` answer type. No change. |
| xml_snippet_matching.py | internal | `NAMESPACES`, `SECURE_PARSER`, `parse_snippet()` | Already imported by `word_writer.py`. No change. |

## lxml Optimization Techniques (Relevant to This Change)

### What Matters

1. **Avoid repeated `fromstring` calls on the same XML**. Currently each `build_insertion_xml` call parses `target_context_xml` via `_parse_element_xml()` (line 111-121 of `xml_formatting.py`). In the batch path, the document is already parsed as an lxml tree in `write_answers` -- extract formatting directly from the live tree element instead of re-serializing and re-parsing it.

2. **Use SubElement for tree building** (already done). `build_run_xml` uses `etree.SubElement` for `<w:rPr>`, `<w:rFonts>`, `<w:sz>`, etc. This is the correct approach. SubElement is faster than creating detached elements and appending them.

3. **Single `tostring` call at the end**. The current `write_answers` already serializes the entire tree once at the end (line 179 of `word_writer.py`). This is correct. Do not serialize individual runs -- build them as live elements and append directly.

### What Does NOT Matter

- **`iterparse` / streaming** -- not applicable. Document XML fits in memory (134KB typical). The tree is already fully parsed.
- **Parser reuse** -- the `SECURE_PARSER` is already a module-level singleton, shared across all calls. No improvement available.
- **cElementTree** -- not an option. The project uses lxml-specific features (Clark notation, namespace maps, `getparent()`). cET lacks these.
- **`copy.deepcopy` optimization** -- not relevant. We build new `<w:r>` elements, we do not copy existing ones.

### Key Optimization: Extract Formatting from Live Tree

Current flow (30 round trips):
```
Agent gets target_context_xml string for each answer
Agent calls build_insertion_xml(answer_text, target_context_xml)  # x30
  -> fromstring(target_context_xml)  # parse string to element
  -> _find_run_properties(elem)      # find <w:rPr>
  -> extract font/size/color/bold    # read attributes
  -> build_run_xml(text, formatting) # create <w:r> element
  -> tostring(r_elem)                # serialize back to string
Agent collects 30 insertion_xml strings
Agent calls write_answers with 30 {xpath, insertion_xml} pairs
  -> fromstring(doc_xml)             # parse full document
  -> for each answer:
       -> parse_snippet(insertion_xml)  # parse EACH insertion_xml string again
       -> target.append(new_elem)       # insert into tree
  -> tostring(root)                     # serialize entire tree
```

Optimized flow (0 round trips for build_insertion_xml):
```
Agent calls write_answers with 30 {xpath, answer_text} pairs
  -> fromstring(doc_xml)             # parse full document ONCE
  -> for each answer:
       -> xpath lookup -> target element (already in tree)
       -> _find_run_properties(target)   # extract from LIVE element, no parsing
       -> build <w:r> as live element    # SubElement, no serialization
       -> target.append(r_elem)          # insert directly into tree
  -> tostring(root)                     # serialize entire tree ONCE
```

This eliminates: 30 `fromstring` calls for target_context_xml, 30 `tostring` calls for insertion_xml, 30 `parse_snippet` calls in write_answers. All replaced by direct element access.

## MCP Protocol Patterns for Batch Operations

### Why No Protocol-Level Batch Exists

The MCP spec (2025-11-25) supports JSON-RPC 2.0 batching at the transport layer, but no mainstream MCP client (Claude Desktop, Claude Code, Cursor, Windsurf, OpenAI) implements it for `tools/call`. Each tool invocation is a separate request-response cycle. The `mcp-batchit` project exists as a workaround aggregator, but it is an external proxy server -- not something to integrate into our server.

### The Correct Pattern: Combined Tool

The standard MCP pattern for reducing round trips is designing tools that accept batch inputs natively. This is already partially implemented in `write_answers` (accepts an array of answers). The fix extends this pattern to accept `answer_text` alongside or instead of `insertion_xml`.

### Backward Compatibility Strategy

The existing `build_insertion_xml` tool MUST remain available because:
1. Agents using `structured` answer type need it (AI-provided OOXML, not plain text)
2. Existing agent workflows depend on it
3. It serves as a debugging/inspection tool

The new batch path adds a parallel code path inside `write_answers`, not a replacement.

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Inline formatting in write_answers | New `batch_build_insertion_xml` tool | Still requires an extra MCP round trip. Goal is zero extra round trips for plain text answers. |
| Keep lxml element-level operations | Template XML strings with f-strings | Fragile, no namespace handling, XML injection risk, harder to maintain. |
| Optional `answer_text` field on AnswerPayload | New model class like BatchAnswer | More disruption to existing code. Optional field preserves backward compat. |
| Extract formatting from live XPath target | Pass id_to_xpath into write_answers for lookup | id_to_xpath is already available from extract_structure_compact. But formatting extraction needs the actual element, not just its XPath. The live tree already has the element after XPath lookup. |

## What NOT to Add

| Avoid | Why | Do Instead |
|-------|-----|------------|
| fastmcp (standalone package) | The project uses `mcp.server.fastmcp.FastMCP` from the official MCP SDK. The standalone `fastmcp` package (v2.x/3.x by jlowin) is a separate project with different APIs. Mixing them causes import conflicts. | Stay on `mcp>=1.23.0` from pyproject.toml |
| mcp-batchit or similar proxy | Adds deployment complexity, another process to manage, and does not reduce the actual computation overhead -- only aggregates calls. | Inline the batch logic inside the server itself |
| cElementTree | Lacks lxml-specific features (Clark notation, getparent, namespace-aware XPath). Would require rewriting xml_snippet_matching.py, xml_formatting.py, and xml_validation.py. | Continue using lxml 6.0.2 |
| async processing inside write_answers | The operations are CPU-bound (XML tree manipulation), not I/O-bound. Python's GIL means async/threading provides zero speedup for lxml element creation. | Keep synchronous processing; the total CPU time for 30 answers is ~26ms |
| XML template caching / memoization | Formatting varies per target element (different cells have different fonts/sizes). Caching would require invalidation logic that adds complexity for negligible gain. | Extract formatting fresh for each target from the live tree |

## Implementation Integration Points

### Files That Change

| File | What Changes | Lines Affected |
|------|-------------|----------------|
| `src/models.py` | Add optional `answer_text: str = ""` to `AnswerPayload` | ~3 lines added |
| `src/handlers/word_writer.py` | Import `_find_run_properties` and `_apply_*` helpers from `xml_formatting`. Add `_build_run_element()` helper that works on live tree elements. Modify `_apply_answer()` to build XML inline when `answer_text` is provided and `insertion_xml` is empty. | ~25 lines added |
| `src/tool_errors.py` | Allow `answer_text` as known field in Word payload validation | ~3 lines changed |
| `src/tools_extract.py` | `build_insertion_xml` tool remains unchanged | 0 lines |
| `src/tools_write.py` | `write_answers` tool unchanged (passes through to handler) | 0 lines |

### Files That Do NOT Change

| File | Why Not |
|------|---------|
| `src/xml_formatting.py` | Functions are already importable. A new variant that accepts a live element (instead of an XML string) belongs in word_writer.py to keep xml_formatting.py focused on its original string-in/string-out contract. |
| `src/xml_validation.py` | Only used for structured answer type, which is unchanged. |
| `src/handlers/word_indexer.py` | Extraction path unchanged. |
| `src/handlers/word_parser.py` | Parsing unchanged. |
| `src/mcp_app.py` | No new tools registered. |

### New Helper Function Signature

```python
# In word_writer.py
def _build_run_element(
    target: etree._Element, answer_text: str
) -> etree._Element:
    """Build a <w:r> element inheriting formatting from the target element.

    Extracts run properties directly from the live tree element,
    avoiding serialization/re-parsing overhead. Returns a live lxml
    element ready to append into the tree.
    """
```

This function reuses `_find_run_properties` and the formatting-application helpers from `xml_formatting.py` but works on live elements instead of serialized XML strings.

## Version Compatibility

| Package | Current | Minimum Required | Notes |
|---------|---------|-----------------|-------|
| lxml | 6.0.2 | >=4.9.1 (per pyproject.toml) | 6.0.x adds zero-copy parsing from memoryview, but not relevant here. No API changes affect this work. |
| mcp | 1.26.0 | >=1.23.0 (per pyproject.toml) | FastMCP decorator API stable since 1.0. No changes needed. |
| pydantic | 2.12.5 | >=2.4.0 (per pyproject.toml) | Optional fields with defaults work in all 2.x versions. |
| python-docx | 1.2.0 | >=1.0.0 | Not involved in this change. |

## Sources

### Official Documentation (HIGH confidence)
- [lxml Performance Benchmarks](https://lxml.de/performance.html) -- SubElement creation ~0.86ms/pass, serialization faster than alternatives. Confirms SubElement approach is correct.
- [lxml 6.0.0 Release Notes](https://lxml.de/6.0/changes-6.0.0.html) -- zero-copy memoryview parsing, decompress=False option. No breaking changes affecting this work.
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) -- JSON-RPC batching at transport level, but no client implements batch tools/call.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) -- v1.26.0 (Jan 2026). FastMCP integrated. No batch tool API.

### Community Patterns (MEDIUM confidence)
- [mcp-batchit](https://github.com/ryanjoachim/mcp-batchit) -- External proxy approach for batching. Validates that no native batch mechanism exists in MCP protocol.
- [lxml Tutorial](https://lxml.de/tutorial.html) -- SubElement usage patterns, tree manipulation best practices.

### Direct Code Analysis (HIGH confidence)
- `src/xml_formatting.py` -- `extract_formatting()` (line 124), `build_run_xml()` (line 178), `_find_run_properties()` (line 31). Pure functions, no state, directly reusable.
- `src/handlers/word_writer.py` -- `write_answers()` (line 162), `_apply_answer()` (line 143). XPath lookup already produces live tree element. Formatting extraction can hook in here.
- `src/tools_extract.py` -- `build_insertion_xml` tool (line 161). Remains unchanged for backward compatibility.
- `src/models.py` -- `AnswerPayload` (line 126). Adding optional `answer_text` field is the minimal model change.

---
*Stack research for: MCP form-filler batch XML generation (round-trip reduction)*
*Researched: 2026-02-17*
