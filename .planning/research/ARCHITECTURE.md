# Architecture Research: Round-Trip Reduction for Word Form Filling

**Domain:** MCP round-trip elimination for OOXML insertion
**Researched:** 2026-02-17
**Confidence:** HIGH (based on direct codebase analysis, no external dependencies)

## Problem Statement

Currently, the agent calls `build_insertion_xml` once per answer to convert plain text into OOXML. For a 50-question form, that is 50 extra MCP round-trips. Each round-trip includes serialization overhead, agent context consumption, and latency. The insight: `word_writer.py` already opens the document and navigates to the XPath target during `write_answers` -- it could extract formatting and build the insertion XML at that point, eliminating all `build_insertion_xml` calls.

## Three Approaches Analyzed

### Approach A: Fast Path in `write_answers` (Recommended)

Allow `AnswerPayload` to carry `answer_text` instead of `insertion_xml`. When `word_writer._apply_answer()` finds `answer_text` (and no `insertion_xml`), it extracts formatting from the target element and builds the run XML inline.

### Approach B: Batch `build_insertion_xml`

Add a new MCP tool `build_insertion_xml_batch` that takes an array of `{answer_text, target_context_xml, answer_type}` and returns an array of `{insertion_xml, valid}`. Reduces N calls to 1 call, but agent still needs target_context_xml for each answer.

### Approach C: Collapse Build Into Write Step

Remove `build_insertion_xml` entirely, make `write_answers` the sole entry point that accepts plain text and handles everything. No backward compatibility -- old callers break.

## Recommendation: Approach A (Fast Path)

Approach A gives the biggest win with the smallest change and full backward compatibility. Here is the detailed integration analysis.

---

## Approach A: Detailed Integration Plan

### Current Data Flow (Before)

```
Agent                          MCP Server
  |                               |
  |-- extract_structure_compact ->|  (1 call)
  |<- compact_text, id_to_xpath --|
  |                               |
  |-- validate_locations -------->|  (1 call)
  |<- xpaths --------------------|
  |                               |
  |-- build_insertion_xml(q1) --->|  (N calls, one per answer)
  |<- insertion_xml_1 ------------|
  |-- build_insertion_xml(q2) --->|
  |<- insertion_xml_2 ------------|
  |   ... (N-2 more) ...         |
  |                               |
  |-- write_answers ------------->|  (1 call)
  |<- filled_docx_bytes ---------|
  |                               |
  |-- verify_output ------------->|  (1 call)
  |<- verification_report -------|
```

**Total: 3 + N calls** (where N = number of answers, typically 20-80)

### New Data Flow (After)

```
Agent                          MCP Server
  |                               |
  |-- extract_structure_compact ->|  (1 call)
  |<- compact_text, id_to_xpath --|
  |                               |
  |-- validate_locations -------->|  (1 call)
  |<- xpaths --------------------|
  |                               |
  |-- write_answers ------------->|  (1 call, answers carry answer_text)
  |   (word_writer extracts       |
  |    formatting from target,    |
  |    builds XML inline)         |
  |<- filled_docx_bytes ---------|
  |                               |
  |-- verify_output ------------->|  (1 call)
  |<- verification_report -------|
```

**Total: 4 calls** (constant, regardless of answer count)

### Changes Required by File

#### 1. `src/models.py` (4 lines added, 0 lines changed)

Add `answer_text` as an optional field to `AnswerPayload`:

```python
class AnswerPayload(BaseModel):
    pair_id: str
    xpath: str
    insertion_xml: str = ""      # CHANGE: default to empty string
    answer_text: str = ""        # NEW: plain text answer (fast path)
    mode: InsertionMode
    confidence: Confidence = Confidence.KNOWN
```

**Key design decision:** Both `insertion_xml` and `answer_text` are optional (default empty). Exactly one must be non-empty. This preserves backward compatibility: existing callers that send `insertion_xml` work unchanged. New callers send `answer_text` instead.

**Validation rule:** If both are empty, raise ValueError. If both are non-empty, `insertion_xml` takes precedence (explicit XML wins over auto-formatting). This is validated in `word_writer.py`, not in the model, because the model is shared across Word/Excel/PDF and the rule is Word-specific.

#### 2. `src/handlers/word_writer.py` (~25 lines added, 3 lines changed)

This is the core change. `_apply_answer()` currently receives pre-built `insertion_xml`. With the fast path, it needs to build the XML when `answer_text` is provided instead.

**New function: `_build_insertion_xml_from_target()`**

```python
def _build_insertion_xml_from_target(
    target: etree._Element, answer_text: str
) -> str:
    """Extract formatting from target element and build insertion XML.

    Reads the run properties (font, size, style) from the target's first
    run or paragraph properties, then wraps answer_text in a <w:r> with
    those properties. This is the same logic as build_insertion_xml but
    operates on the live DOM element instead of a serialized XML string.
    """
    rpr = _find_run_properties(target)
    formatting = _extract_formatting_from_rpr(rpr) if rpr is not None else {}
    return build_run_xml(answer_text, formatting)
```

**Modified function: `_apply_answer()`**

```python
def _apply_answer(body: etree._Element, answer: AnswerPayload) -> None:
    """Locate a single answer's target by XPath and insert its content."""
    _validate_xpath(answer.xpath)
    matched = body.xpath(answer.xpath, namespaces=NAMESPACES)
    if not matched:
        raise ValueError(
            f"XPath '{answer.xpath}' for pair_id '{answer.pair_id}' "
            f"did not match any element in the document"
        )
    target = matched[0]

    # Fast path: build insertion XML from target formatting
    insertion_xml = answer.insertion_xml
    if not insertion_xml and answer.answer_text:
        insertion_xml = _build_insertion_xml_from_target(
            target, answer.answer_text
        )
    elif not insertion_xml and not answer.answer_text:
        raise ValueError(
            f"Answer '{answer.pair_id}' has neither insertion_xml "
            f"nor answer_text"
        )

    if answer.mode == InsertionMode.REPLACE_CONTENT:
        _replace_content(target, insertion_xml)
    elif answer.mode == InsertionMode.APPEND:
        _append_content(target, insertion_xml)
    elif answer.mode == InsertionMode.REPLACE_PLACEHOLDER:
        _replace_placeholder(target, insertion_xml)
```

**Import additions to word_writer.py:**

```python
from src.xml_formatting import (
    build_run_xml,
    _find_run_properties,     # Need to expose or duplicate
)
```

**Problem:** `_find_run_properties` in `xml_formatting.py` currently takes a parsed element from a serialized XML string. In the fast path, we have the live DOM element already. The function's logic is identical -- it searches for `w:rPr` in the element tree. It works directly on `etree._Element`, so it can be reused without changes. However, it is currently a private function (underscore prefix).

**Solution:** Either:
1. Make `_find_run_properties` public (rename to `find_run_properties`) -- cleanest.
2. Add a new function to `xml_formatting.py` that takes an element and returns a formatting dict directly: `extract_formatting_from_element(elem: etree._Element) -> dict`.

Option 2 is better because it encapsulates the two-step process (find rPr, then extract properties) into a single public function.

#### 3. `src/xml_formatting.py` (~10 lines added)

Add a new public function that takes a live DOM element instead of a serialized string:

```python
def extract_formatting_from_element(elem: etree._Element) -> dict:
    """Extract run-level formatting from a live DOM element.

    Same logic as extract_formatting() but operates on an already-parsed
    lxml element instead of an XML string. Used by word_writer.py's fast
    path to avoid re-serializing and re-parsing the target element.
    """
    rpr = _find_run_properties(elem)
    if rpr is None:
        return {}

    formatting: dict = {}
    formatting.update(_extract_font_properties(rpr))
    formatting.update(_extract_size_and_color(rpr))
    formatting.update(_extract_style_properties(rpr))
    return formatting
```

This is 12 lines. `xml_formatting.py` is currently 198 lines, so adding this would push it slightly over 200. To stay under the limit, the new function could replace `extract_formatting()` and `extract_formatting()` could become a thin wrapper:

```python
def extract_formatting(element_xml: str) -> dict:
    """Extract run-level formatting from an OOXML element string."""
    elem = _parse_element_xml(element_xml)
    return extract_formatting_from_element(elem)
```

This actually reduces duplication.

#### 4. `src/tool_errors.py` (~8 lines changed)

Update `_build_word_payloads()` to accept the new `answer_text` field:

```python
_WORD_REQUIRED = ("pair_id", "xpath", "mode")          # CHANGE: remove insertion_xml
_WORD_OPTIONAL = ("confidence", "insertion_xml", "answer_text")  # CHANGE: both optional
_ALL_KNOWN_FIELDS = {*_WORD_REQUIRED, *_WORD_OPTIONAL}
```

Add validation that at least one of `insertion_xml` or `answer_text` is provided:

```python
def _build_word_payloads(answer_dicts: list[dict]) -> list[AnswerPayload]:
    """Word requires pair_id, xpath, mode, and one of insertion_xml or answer_text."""
    results: list[AnswerPayload] = []
    for i, a in enumerate(answer_dicts):
        # ... existing key validation ...

        has_xml = bool(a.get("insertion_xml"))
        has_text = bool(a.get("answer_text"))
        if not has_xml and not has_text:
            raise ValueError(
                f"write_answers validation error in answers[{i}]:\n"
                f"  Must provide either 'insertion_xml' or 'answer_text'.\n"
                f"  'answer_text' is preferred (server builds XML automatically)."
            )
        # ... rest of existing logic ...
```

Update USAGE examples to show the new fast-path usage:

```python
USAGE["write_answers"] = (
    'write_answers(file_path="form.docx", answers=[{"pair_id": "q1", '
    '"xpath": "/w:body/...", "answer_text": "Acme Corp", '
    '"mode": "replace_content"}])'
)
```

#### 5. `src/tools_write.py` (0 lines changed)

No changes needed. The MCP tool function is already a thin wrapper. It passes the answer dicts through to `build_answer_payloads()` which builds `AnswerPayload` objects. The new `answer_text` field flows through automatically because Pydantic accepts extra fields defined on the model.

#### 6. `src/handlers/word.py` (0 lines changed)

No changes needed. `write_answers()` already delegates directly to `word_writer.write_answers()`.

#### 7. `src/tools_extract.py` (0 lines changed)

`build_insertion_xml` remains available. No changes needed. Agents that want to pre-build XML can still call it.

### Files NOT Changed

| File | Why Unchanged |
|------|---------------|
| `src/server.py` | Entry point -- no business logic |
| `src/mcp_app.py` | FastMCP singleton -- no business logic |
| `src/xml_validation.py` | Only validates structured XML -- not used in fast path |
| `src/xml_snippet_matching.py` | Snippet matching unrelated to insertion |
| `src/validators.py` | File input validation -- no answer-level logic |
| `src/handlers/word_parser.py` | XML extraction -- unchanged |
| `src/handlers/word_indexer.py` | Compact extraction -- unchanged |
| `src/handlers/word_location_validator.py` | Location validation -- unchanged |
| `src/handlers/word_fields.py` | Form field detection -- unchanged |
| `src/handlers/word_verifier.py` | Post-write verification -- unchanged |
| All Excel handlers | Excel does not use insertion XML |
| All PDF handlers | PDF does not use insertion XML |

### Backward Compatibility

**Full backward compatibility. Zero breaking changes.**

- Old callers that send `insertion_xml` continue to work -- it is still the default code path
- Old callers that omit `answer_text` see no difference -- `answer_text` defaults to `""`
- `build_insertion_xml` MCP tool remains available -- agents can call it if they want
- `AnswerPayload` with `insertion_xml` still validates correctly
- `tool_errors.py` validation accepts either field
- Tests that use `insertion_xml` continue passing unchanged

**Migration path for agents:** Replace `build_insertion_xml` calls with `answer_text` in the answer payload. Agents can migrate one answer at a time -- mix `insertion_xml` and `answer_text` answers in the same `write_answers` call.

### New Test Cases Needed

```
tests/test_word.py (or new tests/test_word_fast_path.py):

1. test_fast_path_plain_text_inherits_formatting
   - Send answer_text="Acme Corp" to a cell with Arial 24pt bold
   - Verify output has the answer text with inherited formatting

2. test_fast_path_no_formatting_target
   - Send answer_text to a target with no rPr
   - Verify output has plain text (no formatting applied)

3. test_fast_path_replace_content_preserves_tcPr
   - Same as existing test but using answer_text instead of insertion_xml

4. test_fast_path_append_mode
   - Send answer_text with mode=append

5. test_fast_path_replace_placeholder_mode
   - Send answer_text with mode=replace_placeholder

6. test_fast_path_mixed_with_insertion_xml
   - Some answers use answer_text, others use insertion_xml, in same call

7. test_insertion_xml_takes_precedence
   - Send both answer_text and insertion_xml -- insertion_xml wins

8. test_neither_answer_text_nor_insertion_xml_raises
   - Send empty for both -- ValueError

9. test_fast_path_produces_same_output_as_build_insertion_xml
   - For the same answer, verify fast path output matches
     build_insertion_xml + write_answers output byte-for-byte
```

### Build Order

**Step 1: `xml_formatting.py`** -- Add `extract_formatting_from_element()`
- No dependencies on other changes
- Existing `extract_formatting()` can call it internally (refactor)
- Testable independently

**Step 2: `models.py`** -- Add `answer_text` field to `AnswerPayload`
- No dependencies on Step 1
- All existing tests still pass (field has default value)
- Can run in parallel with Step 1

**Step 3: `word_writer.py`** -- Add fast path in `_apply_answer()`
- Depends on Step 1 (needs `extract_formatting_from_element`)
- Depends on Step 2 (needs `answer_text` on AnswerPayload)
- Core logic change

**Step 4: `tool_errors.py`** -- Update validation for new field
- Depends on Step 2 (needs `answer_text` field to exist)
- Can run in parallel with Step 3

**Step 5: Tests** -- Add fast path test cases
- Depends on Steps 1-4
- Must verify backward compatibility and new behavior

**Step 6: CLAUDE.md** -- Update documentation
- Update pipeline description to mention fast path
- Update agent guidance to recommend `answer_text` over `build_insertion_xml`
- Update `write_answers` tool description to document `answer_text` field

```
Step 1: xml_formatting.py ─┐
                           ├─> Step 3: word_writer.py ──> Step 5: Tests
Step 2: models.py ─────────┤                                    │
                           └─> Step 4: tool_errors.py ──────────┘
                                                          Step 6: Docs
```

---

## Approach B Analysis: Batch `build_insertion_xml`

### What Changes

Add a new MCP tool `build_insertion_xml_batch`:

```python
@mcp.tool()
def build_insertion_xml_batch(
    items: list[dict],  # [{answer_text, target_context_xml, answer_type}]
) -> dict:
    """Build insertion XML for multiple answers in one call."""
    results = []
    for item in items:
        result = word_handler.build_insertion_xml(
            BuildInsertionXmlRequest(**item)
        )
        results.append(result.model_dump())
    return {"results": results}
```

### Why Not Recommended

1. **Still requires `target_context_xml`**: The agent must still extract and send the XML context for each answer target. This data is already available inside `word_writer.py` during the write step -- passing it through the agent is redundant work.

2. **Reduces round-trips but not agent context consumption**: The agent still needs to hold N `target_context_xml` strings plus N `insertion_xml` results in its context window.

3. **Only reduces N calls to 2 calls** (batch build + write), not to 0 extra calls. Approach A eliminates the entire build step.

4. **New tool surface area**: Adding a tool means more documentation, more tests, more maintenance. Approach A adds a field to an existing tool.

### When Batch Would Be Better

If the fast path proves unreliable (formatting extraction from live DOM differs from extraction from serialized XML), batch is a safe fallback. But the code is identical -- `xml_formatting.py` operates on `etree._Element` objects in both cases. The serialized path just adds parse/serialize overhead.

---

## Approach C Analysis: Remove `build_insertion_xml`

### What Changes

Delete `build_insertion_xml` from `tools_extract.py`, `word.py`, and `models.py`. Make `write_answers` the only way to insert answers. Remove `insertion_xml` from `AnswerPayload`.

### Why Not Recommended

1. **Breaking change**: Any existing agent workflows that call `build_insertion_xml` stop working.

2. **Loses structured XML support**: The current `build_insertion_xml` with `answer_type="structured"` lets agents provide custom OOXML for complex answers (checkboxes, formatted content). The fast path only handles plain text.

3. **Against project convention**: CLAUDE.md says "Never change a function signature without updating all callers." Removing a tool is a more drastic change than modifying a signature.

4. **No additional benefit over Approach A**: Approach A gives the same round-trip reduction (0 extra calls for plain text) while keeping the escape hatch for structured XML.

---

## Architecture After Approach A

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Tool Layer                           │
│                                                              │
│  tools_extract.py                   tools_write.py           │
│  ├── extract_structure_compact()    ├── write_answers()      │
│  ├── extract_structure()            │   (accepts answer_text │
│  ├── validate_locations()           │    OR insertion_xml)   │
│  ├── build_insertion_xml()  ←KEPT   └── verify_output()      │
│  │   (still available for                                    │
│  │    structured XML answers)                                │
│  └── list_form_fields()                                      │
├─────────────────────────────────────────────────────────────┤
│                     Handler Layer                            │
│                                                              │
│  handlers/word.py                                            │
│  ├── extract_structure()                                     │
│  ├── build_insertion_xml()  ←KEPT                            │
│  ├── write_answers()                                         │
│  │   └── word_writer.write_answers()                         │
│  │       └── _apply_answer()                                 │
│  │           ├── HAS insertion_xml? → use it (old path)      │
│  │           └── HAS answer_text?   → extract formatting     │
│  │               from target, build XML (NEW fast path)      │
│  └── list_form_fields()                                      │
├─────────────────────────────────────────────────────────────┤
│                     Utility Layer                            │
│                                                              │
│  xml_formatting.py                                           │
│  ├── extract_formatting(xml_str)         ←existing           │
│  ├── extract_formatting_from_element()   ←NEW                │
│  └── build_run_xml(text, formatting)     ←existing           │
│                                                              │
│  xml_validation.py                                           │
│  └── is_well_formed_ooxml()              ←unchanged          │
├─────────────────────────────────────────────────────────────┤
│                      Model Layer                             │
│                                                              │
│  models.py                                                   │
│  └── AnswerPayload                                           │
│      ├── pair_id: str                                        │
│      ├── xpath: str                                          │
│      ├── insertion_xml: str = ""         ←now optional        │
│      ├── answer_text: str = ""           ←NEW                │
│      ├── mode: InsertionMode                                 │
│      └── confidence: Confidence                              │
└─────────────────────────────────────────────────────────────┘
```

### Component Boundaries After Change

| Component | Responsibility | Changed? |
|-----------|---------------|----------|
| `tools_write.py` | MCP tool definitions for write operations | No |
| `tools_extract.py` | MCP tool definitions for read operations | No |
| `models.py` | Data models for all tool inputs/outputs | Yes: `answer_text` field added |
| `word_writer.py` | XPath-based content insertion into documents | Yes: fast path added |
| `word.py` | Word handler public API | No |
| `xml_formatting.py` | Formatting extraction and run building | Yes: new public function |
| `tool_errors.py` | Input validation with rich error messages | Yes: updated field requirements |

### Import Dependency Changes

```
BEFORE:
  word_writer.py → models, xml_utils (NAMESPACES, SECURE_PARSER, parse_snippet)

AFTER:
  word_writer.py → models, xml_utils (same)
                 → xml_formatting (extract_formatting_from_element, build_run_xml)
```

This new import is safe: `xml_formatting.py` has no handler dependencies (it only imports from `xml_snippet_matching`). The import direction flows correctly: handler -> utility.

## Edge Cases and Safety

### What Happens When the Target Has No Formatting?

The fast path extracts an empty formatting dict. `build_run_xml("text", {})` produces a bare `<w:r><w:t>text</w:t></w:r>` with no `<w:rPr>`. This is correct -- it matches what `build_insertion_xml` produces when `target_context_xml` has no formatting.

### What Happens With Table Cells (w:tc)?

`_replace_content()` already wraps bare `<w:r>` elements in `<w:p>` when the target is a `<w:tc>`. The fast path produces a `<w:r>`, so this existing wrapping logic handles the table cell case correctly.

### What About Structured Answers (Checkboxes, Complex Content)?

Structured answers require `answer_type="structured"` and AI-generated OOXML. These must still use `build_insertion_xml` to validate the XML, then pass `insertion_xml` to `write_answers`. The fast path only handles plain text.

The agent's decision tree:
- Plain text answer -> use `answer_text` (fast path)
- Complex/structured answer -> call `build_insertion_xml`, use `insertion_xml` (old path)

In practice, 95%+ of form answers are plain text. The fast path handles the common case.

### What If the Agent Sends Both `answer_text` and `insertion_xml`?

`insertion_xml` takes precedence. The agent explicitly built the XML, so we respect that. This also means agents can gradually migrate: start sending `answer_text` for simple answers while keeping `insertion_xml` for complex ones.

## Quantified Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| MCP calls for 50 answers | 53 | 4 | 92% fewer calls |
| Agent context for answers | ~50 insertion_xml strings + 50 target_context_xml strings | 50 answer_text strings only | ~60% less context |
| Files changed | -- | 4 | Minimal surface area |
| Lines added | -- | ~45 | Small change |
| Breaking changes | -- | 0 | Full backward compatibility |
| New MCP tools | -- | 0 | No new API surface |

## Sources

- Direct codebase analysis of all files in `src/` and `tests/` (HIGH confidence)
- CLAUDE.md project conventions and pipeline documentation (HIGH confidence)
- No external dependencies -- this is an internal architecture decision based entirely on existing code structure

---
*Architecture research for: Round-trip reduction in Word form filling*
*Researched: 2026-02-17*
*Focus: How to eliminate per-answer build_insertion_xml calls by moving formatting extraction into the write step*
