# Pitfalls Research

**Domain:** Batch/Fast-Path Operations for MCP Form Filler Round-Trip Reduction
**Researched:** 2026-02-17
**Confidence:** HIGH (based on deep codebase analysis plus OOXML specification research)

## Critical Pitfalls

### Pitfall 1: Formatting Extraction Divergence Between Snippet and Full Element

**What goes wrong:**
Currently `extract_formatting()` in `xml_formatting.py` receives a `target_context_xml` string -- an OOXML snippet the agent extracted or received from `validate_locations`. The function calls `_find_run_properties()` which searches: direct child rPr, first run's rPr, then pPr's rPr. If the server instead builds XML at write-time using the full element at the XPath, formatting extraction may produce different results because:

1. The full element at an XPath like `./w:tbl[1]/w:tr[2]/w:tc[2]/w:p[1]` is a `<w:p>` containing zero or more runs. An empty cell's paragraph has NO runs and NO rPr -- `extract_formatting()` returns `{}` (no formatting).
2. But the same empty cell's *parent* `<w:tc>` may have `<w:tcPr>` with formatting, or the table style may apply conditional formatting. The current snippet-based path never sees this because the agent sends a paragraph-level snippet, not the cell.
3. If the server reads the full element at write-time, it gets the `<w:p>` -- still no formatting. But if someone "improves" this to walk up to the parent `<w:tc>` or `<w:tbl>` to find inherited formatting, the formatting output changes for every empty cell.

**Why it happens:**
OOXML has a 5-level style hierarchy: document defaults -> table style -> numbering -> paragraph style -> direct formatting. The current system only extracts direct formatting (level 5) from whatever snippet the agent provides. This is consistent and correct for the current design. The danger is that when moving formatting extraction server-side during write, someone resolves more of the hierarchy "to be more correct," producing different output than the current path and breaking backward compatibility.

**How to avoid:**
- The fast-path formatting extraction MUST use the exact same `_find_run_properties()` logic from `xml_formatting.py`. Do not "improve" it by walking up the element tree.
- Scope the extraction to the same element boundary: if the XPath points to a `<w:p>`, extract from that `<w:p>` only, not its parent `<w:tc>`.
- Add a comparison test: for every answer in a fixture document, run both paths (agent snippet path and server fast-path) and assert identical `insertion_xml` output. Any divergence is a bug in the fast path.
- Document explicitly: "Formatting extraction reads only direct rPr from the target element. Style inheritance is intentionally not resolved."

**Warning signs:**
- Previously empty-cell answers had no formatting (plain text), but after the change they suddenly inherit the table's font/size
- `verify_output` starts reporting mismatches on formatting-sensitive comparisons
- Tests pass but real-world documents show answers in different fonts than before
- The fast-path produces `<w:rPr>` elements where the old path produced none (or vice versa)

**Phase to address:**
Phase 1: Fast-path implementation (formatting extraction parity tests)

---

### Pitfall 2: Structured Answer Type Cannot Be Collapsed

**What goes wrong:**
When designing the batch/fast-path, a developer sees that `build_insertion_xml` for `plain_text` can be folded into `write_answers` (server reads element at XPath, extracts formatting, builds run XML, inserts it). They then try to also fold `structured` answers the same way. But `structured` answers are fundamentally different: the agent provides raw OOXML, the server only validates it. There is no formatting to extract and no XML to build -- the agent IS the builder. Folding structured answers into the fast path would mean the agent stops providing XML, which removes a capability.

Even worse: the agent using compact extraction (element IDs like `T1-R2-C1`) typically does NOT have `target_context_xml` available. They have an element ID and an answer string. The fast path is designed exactly for this case: `{element_id, answer_text}` -> server resolves XPath, extracts formatting, builds XML, writes. But if someone conflates this with the structured path, the API becomes confused about who owns XML construction.

**Why it happens:**
The two answer types share a function name (`build_insertion_xml`) which suggests they are variations of the same operation. In reality they are opposite operations: one is "server builds XML" and the other is "server validates agent-built XML." Collapsing them into one batch call without understanding this distinction breaks the structured path.

**How to avoid:**
- The batch/fast-path API should explicitly support only `plain_text` answers. Structured answers continue to use the existing per-item `build_insertion_xml` tool.
- In the batch request model, include an `answer_type` field with a clear error if someone passes `structured` without `insertion_xml`.
- Document: "The fast path handles plain_text answers only. For structured answers (checkboxes, complex formatting), use build_insertion_xml separately."
- Consider allowing a hybrid batch: most answers are `{element_id, answer_text}` (fast path) but some can be `{element_id, insertion_xml}` (pre-built, skip formatting extraction).

**Warning signs:**
- Batch API accepts `structured` type but silently ignores agent-provided XML
- Agent sends `answer_type: "structured"` with raw OOXML in `answer_text`, batch path treats it as plain text and double-wraps it in `<w:r>`
- Tests only cover plain_text batch -- structured is untested and broken
- Agent documentation says "use batch for everything" without mentioning the structured exception

**Phase to address:**
Phase 1: API design (answer type routing in batch schema)

---

### Pitfall 3: Element ID to XPath Resolution Parses Document Twice

**What goes wrong:**
The current `validate_locations` already re-runs `extract_structure_compact` (which parses the full .docx) when any element ID is present, to get the `id_to_xpath` mapping. If `write_answers` also needs to resolve element IDs to XPaths and extract formatting from the elements at those XPaths, the document gets parsed three times for a typical fast-path flow: once in `validate_locations`, once to resolve IDs in `write_answers`, and once more to locate elements for formatting extraction. For a 50-answer form, this adds seconds of overhead that defeats the purpose of reducing round-trips.

**Why it happens:**
The server is stateless -- each tool call re-reads the document from bytes. This is correct and intentional for the current per-item pipeline. But when consolidating multiple steps into one batch call, the stateless design means you must either: (a) parse once and pass the tree through internally, or (b) accept redundant parsing.

**How to avoid:**
- The batch `write_answers` call should parse the document once, build the `id_to_xpath` mapping once, and resolve all elements in a single tree walk.
- Do NOT add state between tool calls (e.g., caching parsed trees across MCP calls). Keep stateless design.
- Instead, make the batch call internally efficient: parse .docx -> build xpath map -> for each answer: resolve xpath, find element, extract rPr, build run XML, insert -> repackage once.
- The separate `validate_locations` call becomes optional for the fast path -- the batch `write_answers` validates as it writes and reports failures per-answer in the response.

**Warning signs:**
- Large forms (50+ answers) take 10+ seconds for `write_answers` when the old per-item path took 3 seconds total
- CPU profiling shows 80% time in ZIP decompression and XML parsing, not in actual insertion
- Memory spikes from holding multiple copies of the same parsed tree

**Phase to address:**
Phase 1: Implementation (single-parse architecture for batch write)

---

### Pitfall 4: xml:space="preserve" Dropped in Server-Built XML for Edge Cases

**What goes wrong:**
The current `build_run_xml()` in `xml_formatting.py` correctly sets `xml:space="preserve"` when the text has leading or trailing spaces (line 194). But the check is `if text and (text[0] == " " or text[-1] == " ")`. This misses edge cases:

1. Text that is entirely whitespace (e.g., a single space " " used as a cell separator) -- this passes the check but is an unusual case worth testing.
2. Tab characters or other whitespace -- OOXML converts non-space whitespace in `<w:t>` to spaces, but tabs should use `<w:tab/>` elements instead.
3. Newline characters in answer text -- should be split into multiple runs with `<w:br/>` elements, not embedded as `\n` in a single `<w:t>`.
4. Empty string answers -- `text` is falsy, so `xml:space` is not set, but an empty `<w:t/>` is still valid OOXML.

When the server builds XML at write-time instead of the agent calling `build_insertion_xml`, the agent may send answers with embedded newlines or tabs that the current `build_run_xml()` does not handle. Currently the agent sees the `build_insertion_xml` response and can adjust; in the fast path, the server silently writes malformed content.

**Why it happens:**
The current `build_run_xml()` was designed for single-line plain text answers. The agent controlled what text it sent and could pre-process it. Moving XML construction server-side means the server must handle all text edge cases because the agent no longer has a chance to inspect the result before it is written.

**How to avoid:**
- Add text normalization to the fast-path XML builder: split on `\n` to create `<w:br/>` elements, convert `\t` to `<w:tab/>`, handle empty strings gracefully.
- Add tests for: `" "` (single space), `"Line1\nLine2"` (embedded newline), `"\t"` (tab), `""` (empty), `"  leading spaces"`, `"trailing spaces  "`.
- The normalization should live in a helper function that both `build_run_xml()` and the fast-path builder share, so behavior is identical.
- Do NOT change existing `build_run_xml()` behavior for backward compatibility -- add a new internal helper that the fast path uses.

**Warning signs:**
- Answers with newlines appear as literal `\n` text in the Word document instead of line breaks
- Tabs appear as spaces in the output document
- Leading/trailing spaces disappear from answers
- `verify_output` shows mismatches because the expected text has spaces but the actual text does not

**Phase to address:**
Phase 1: XML builder enhancement (text normalization for server-side construction)

---

### Pitfall 5: verify_output Text Comparison Breaks with Different XML Structure

**What goes wrong:**
`word_verifier.py` extracts text by iterating all `<w:t>` elements under the target element and joining with spaces. If the fast-path builds XML differently from the agent path (e.g., using multiple `<w:r>` elements where the agent path used one, or adding `<w:br/>` elements for newlines), the extracted text changes. This causes `verify_output` to report mismatches even though the document is correct.

Specific failure modes:
1. Agent path: one `<w:r>` with one `<w:t>` containing "Acme Corp". Fast path: two `<w:r>` elements (split for formatting). Verifier extracts "Acme Corp" (two `<w:t>` elements joined with space) -- matches.
2. Agent path: `<w:t>Acme Corp</w:t>`. Fast path: `<w:t>Acme</w:t>` + `<w:t> Corp</w:t>`. Verifier extracts "Acme  Corp" (two texts joined with space, but one already has leading space) -- mismatch due to double space.
3. Fast path adds `<w:br/>` for newlines. Verifier extracts text without the break. Expected text was "Line1\nLine2" but actual is "Line1 Line2" or "Line1Line2".

**Why it happens:**
The verifier uses a simple text extraction that concatenates `<w:t>` text with space separators. This works when XML structure is predictable (one `<w:r>` per answer, as the agent typically produces). When the server builds XML with different structure, the text extraction algorithm produces different strings even for semantically identical content.

**How to avoid:**
- Update `_extract_text()` in `word_verifier.py` to normalize whitespace: collapse multiple spaces to one, trim, and handle `<w:br/>` as newline.
- OR: keep the verifier unchanged but ensure the fast-path XML builder produces structurally identical output to `build_run_xml()` -- same number of `<w:r>` and `<w:t>` elements.
- Add regression tests: write an answer via the old path, verify. Write the same answer via the fast path, verify. Both must produce identical verification results.
- The safest approach is both: normalize the verifier AND ensure structural parity in the builder.

**Warning signs:**
- `verify_output` reports `mismatched` for answers that are visually correct in the document
- Mismatch rate increases with the fast path but not with the old path
- Mismatches correlate with specific text patterns (spaces, newlines, special characters)

**Phase to address:**
Phase 1: Verification parity tests (run both paths, compare verify_output results)

---

### Pitfall 6: Agent Behavioral Assumption -- build_insertion_xml Returns Are Inspectable

**What goes wrong:**
In the current pipeline, agents call `build_insertion_xml` and receive the insertion XML in the response. Some agents inspect this response to verify it looks correct before passing it to `write_answers`. For example, an agent might check that the font name matches expectations, or that the text content is correct. In the fast path, the agent never sees the insertion XML -- it sends `{element_id, answer_text}` and gets back a filled document. The "inspect before write" pattern is eliminated.

If the agent's workflow depends on inspecting insertion XML (e.g., to retry with different formatting, or to log what was inserted), the fast path removes this capability without the agent realizing it. The agent silently loses its quality control step.

**Why it happens:**
The fast path is designed to reduce round-trips: fewer calls means faster execution. But each round-trip was also a synchronization point where the agent could make decisions. Removing the synchronization point removes the decision point.

**How to avoid:**
- The batch `write_answers` response should include per-answer details: `{pair_id, status, insertion_xml_used, formatting_extracted}`. This gives agents the same information they would have gotten from individual `build_insertion_xml` calls, just after the fact instead of before.
- Document the behavioral change: "The fast path writes answers directly. Agents that need to inspect insertion XML before writing should continue using the per-item build_insertion_xml -> write_answers flow."
- Keep the per-item path fully functional. The fast path is an optimization, not a replacement.
- Never deprecate `build_insertion_xml` -- agents with complex formatting requirements need it.

**Warning signs:**
- Agents that previously worked correctly start producing documents with wrong formatting after switching to the fast path
- Agent logs show "skipping formatting check" or "insertion XML not available"
- Agent prompts that say "verify the XML looks correct before writing" become dead code

**Phase to address:**
Phase 1: API design (response schema includes per-answer insertion details)

---

### Pitfall 7: Batch Write Partial Failure Leaves Document in Inconsistent State

**What goes wrong:**
In the current per-item pipeline, each `write_answers` call processes all answers in a single XML tree manipulation and repackages the ZIP once. If any answer's XPath is invalid, the entire call fails with a `ValueError` before any modifications. But the fast path adds more failure points: element ID resolution (ID not found), formatting extraction (element has unexpected structure), and XML building (text normalization edge case). If answer 25 out of 50 fails after answers 1-24 have already been applied to the in-memory XML tree, the caller gets an error but no document -- all 24 successful insertions are lost.

**Why it happens:**
The current `_apply_answer()` in `word_writer.py` validates the XPath first (`_validate_xpath`) and then does the insertion, but validation and insertion happen sequentially per answer in the `for answer in answers` loop. If answer 3 validates and is applied but answer 4 fails, the partially-modified tree is discarded when the exception propagates. This is the existing behavior, but the fast path makes it worse because there are additional failure modes beyond XPath validation: element ID not found in mapping, formatting extraction failure, and text normalization errors. More failure modes means partial application is more likely.

**How to avoid:**
- Validate ALL answers before applying ANY. Phase 1: resolve all element IDs to XPaths, validate all XPaths, extract all formatting. Phase 2: apply all insertions. If phase 1 fails for any answer, report all failures without modifying the document.
- Return per-answer status in the response: `{pair_id: "success"}` or `{pair_id: "failed", error: "Element ID T99-R1-C1 not found"}`.
- For partial failure, offer a choice: `on_error: "abort"` (default, fail the entire batch) or `on_error: "skip"` (skip failed answers, write successful ones, report which failed).
- The `verify_output` step already exists to catch post-write issues. Document: "Always run verify_output after batch write, especially when using on_error: skip."

**Warning signs:**
- Agent calls batch write with 50 answers, 1 has a bad element ID, entire call fails, no document returned
- Agent retries the entire batch after fixing the one bad answer, wasting time
- No way to know which answer caused the failure without reading the error message carefully
- Agent logs show repeated "write_answers failed" with different error messages each time (because each retry fixes one error but reveals the next)

**Phase to address:**
Phase 1: Error handling design (two-phase validate-then-apply, per-answer status reporting)

---

### Pitfall 8: Compact Extraction Agent Has No target_context_xml

**What goes wrong:**
The `build_insertion_xml` MCP tool requires `target_context_xml` -- an XML snippet showing the target element's formatting. Agents using `extract_structure_compact` get element IDs and human-readable text, NOT XML snippets. They would need to also call `extract_structure` (the raw XML endpoint) to get XML context, which defeats the purpose of compact extraction.

When designing the fast path, this gap is the entire reason the fast path exists: agents using compact extraction cannot call `build_insertion_xml` without an extra round-trip to get XML context. But if the fast-path design does not properly handle this, developers might add a "get context XML for element ID" tool, adding a round-trip instead of eliminating one.

**Why it happens:**
The compact extraction was designed to keep agents away from raw XML. The pipeline was: compact extraction -> validate by ID -> build XML (requires context) -> write. Step 3 creates a problem because the agent needs XML context it does not have. The "correct" solution is to move step 3 into step 4: write_answers accepts element IDs and answer text, builds XML internally.

**How to avoid:**
- The batch `write_answers` must accept element IDs directly: `{element_id: "T1-R2-C2", answer_text: "Acme Corp"}`. The server resolves the ID to XPath, finds the element, extracts formatting, builds XML, and inserts -- all in one call.
- Do NOT add a new tool like `get_element_context(element_id) -> xml`. This adds a round-trip instead of removing one.
- The `id_to_xpath` mapping from compact extraction is the bridge: element ID -> XPath -> locate element in tree -> extract formatting. This must all happen inside `write_answers`.
- Keep `build_insertion_xml` available for agents that need it (those using raw extraction or structured answers). Do not remove it.

**Warning signs:**
- A new MCP tool is proposed that returns XML context for an element ID
- Agent flow gains a step instead of losing one after the "optimization"
- Agents are told to call `extract_structure` alongside `extract_structure_compact` to get context XML
- The batch write tool still requires `insertion_xml` as a parameter (means nothing was collapsed)

**Phase to address:**
Phase 1: API design (batch write accepts element_id + answer_text, resolves internally)

---

### Pitfall 9: Multi-Run Formatting in Target Element Produces Ambiguous Inheritance

**What goes wrong:**
`_find_run_properties()` in `xml_formatting.py` finds the FIRST run's `<w:rPr>` when the element is a paragraph. But many real-world document cells have multiple runs with different formatting: a bold label followed by a normal-weight placeholder, or mixed font sizes. The first run's formatting is not necessarily the "answer formatting" -- often the answer should match the second run (the placeholder text's formatting), not the first (the label's formatting).

Example: A cell containing `<w:r><w:rPr><w:b/></w:rPr><w:t>Name: </w:t></w:r><w:r><w:t>[Enter here]</w:t></w:r>`. The first run is bold (it is the label). The second run is not bold (it is the placeholder). `_find_run_properties()` returns bold formatting, so the answer "Acme Corp" is inserted in bold -- wrong.

This is NOT a new bug -- it exists in the current pipeline too. But moving formatting extraction server-side makes it the server's problem instead of the agent's. An agent using the current path could inspect the insertion XML, see it was bold, and adjust. With the fast path, the bold formatting is silently applied.

**Why it happens:**
`_find_run_properties()` picks the first run as a reasonable default. It has no way to know which run represents the "answer formatting" without understanding the semantic structure of the document.

**How to avoid:**
- For the fast path, prefer the LAST run's formatting when the target paragraph has multiple runs. The last run is more likely to be the placeholder or empty text that the answer replaces.
- Better: if the target element is being cleared (replace_content mode), extract formatting from the last non-empty run, or from the run containing placeholder text.
- Add a heuristic: if any run contains placeholder text (matching `PLACEHOLDER_RE`), use that run's formatting.
- Add test fixtures with multi-run cells (bold label + normal placeholder) and verify the answer inherits the placeholder's formatting, not the label's.
- Document this as a known limitation with the specific heuristic used, so future developers do not "fix" it in a way that breaks other cases.

**Warning signs:**
- Answers appear bold/italic when they should not be
- Formatting differs between answers in different parts of the same form
- Agent-provided answers looked right (agent chose not to inherit formatting), but fast-path answers look wrong (server inherited the wrong run's formatting)

**Phase to address:**
Phase 1: Formatting extraction enhancement (multi-run heuristic)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keeping both per-item and batch paths indefinitely | No migration risk, full backward compat | Two code paths to maintain, potential drift in behavior | **Always acceptable** -- structured answers require the per-item path, so both paths are architecturally necessary |
| Batch write resolves IDs internally without separate validation | Fewer round-trips | Loss of explicit validation step; errors reported at write time instead of validation time | **Acceptable for v1** if per-answer status reporting is thorough |
| Single-run formatting extraction (first or last run heuristic) | Simple implementation, predictable behavior | Wrong formatting for multi-run cells (bold labels, mixed formatting) | **Acceptable for v1** with documented limitation |
| Not resolving OOXML style hierarchy (document defaults, table styles) | Consistent with current behavior, simpler code | Answers in styled documents may lack expected formatting (e.g., document default font not applied) | **Acceptable indefinitely** -- resolving the full hierarchy is a massive undertaking for marginal benefit |
| Skipping formatting extraction for empty cells (returning no rPr) | Correct per OOXML spec -- empty cells have no direct formatting | Answer text in empty cells uses Word's default rendering, which may differ from the question cell | **Acceptable** -- this is correct behavior; "fixing" it by guessing formatting would be worse |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Agent switching from per-item to batch | Sending `structured` answers in batch call expecting server to handle them | Batch handles `plain_text` only; `structured` answers must still use `build_insertion_xml` separately |
| Agent using compact extraction | Assuming `id_to_xpath` mapping from extraction remains valid after document modification | Always use the ORIGINAL document's `id_to_xpath`; XPaths may shift after insertions if element indices change |
| Agent skipping `validate_locations` in fast path | Relying on batch write to catch bad IDs at write time | Batch write should validate all IDs before modifying any content; but agents should still validate early for better UX |
| Agent providing answers with newlines | Expecting `\n` in answer text to become line breaks in the document | Fast path must convert `\n` to `<w:br/>` elements; document this in tool description |
| Agent providing HTML entities in answers | Expecting `&amp;`, `&lt;` to be rendered as literal characters | Server must handle XML escaping; `lxml` does this automatically when setting `.text`, but if text is embedded in an XML string it must be escaped |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Parsing .docx ZIP for each answer in a batch | Linear slowdown with answer count; 50 answers = 50 ZIP reads | Parse once, operate on in-memory tree, repackage once | > 10 answers |
| Re-running compact extraction inside write_answers to get id_to_xpath | Additional 200ms+ per call for document parsing and tree walking | Accept id_to_xpath as a parameter OR build it once internally | > 20 answers |
| Building xpath mapping for ALL elements when only some are needed | O(n) walk of entire document tree when only 5 answers need resolving | Build a lookup for only the requested element IDs using targeted XPath | > 100 elements in document |
| Serializing entire modified XML tree per-answer for debugging | Log output grows quadratically with document size and answer count | Log only element ID, answer text, and status per answer; serialize tree only on error | > 50KB document |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting arbitrary XPath in batch write without validation | XPath injection: agent-provided XPath could evaluate functions, access document properties, or cause DoS via recursive expressions | Continue using `_XPATH_SAFE_RE` validation; apply it to resolved XPaths from element IDs too |
| Trusting element IDs without re-validating against current document | Stale IDs from a previous extraction could point to wrong elements if document was modified between extraction and write | Always re-parse document and verify XPath resolves to an element; never cache resolved elements across tool calls |
| Allowing batch write with uncapped answer count | Memory exhaustion: agent sends 10,000 answers for a 50-cell document | Enforce existing `MAX_ANSWERS` limit in batch path; return clear error |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent formatting difference between per-item and batch paths | User compares documents filled via different paths and gets confused by formatting differences | Ensure parity tests pass; if parity is impossible, document the difference |
| Batch write error message says "XPath not found" without identifying which answer | Agent cannot tell user which question failed; user must re-run entire batch | Per-answer status in response: `{pair_id: "q17", status: "failed", error: "Element T5-R3-C2 not found"}` |
| No progress indication for large batches | Agent appears to hang during a 50-answer batch write | Not applicable for synchronous MCP calls; but response should include timing info and answer count for agent to report |
| Agent told to "use batch for everything" | Agent tries to batch structured answers and gets cryptic errors | Tool description clearly states batch is for plain_text answers only |

## "Looks Done But Isn't" Checklist

- [ ] **Formatting parity:** Both paths produce identical insertion XML for the same answer and target -- verify with a comparison test that runs all fixture answers through both paths
- [ ] **Empty cell handling:** Fast path correctly produces unformatted `<w:r>` for empty cells (no rPr) -- verify with empty cell fixtures
- [ ] **xml:space="preserve":** Fast path sets it for leading/trailing spaces -- verify with `" Acme "` and `"  "` test cases
- [ ] **Structured answer rejection:** Fast path returns clear error when answer_type is "structured" -- verify with explicit test
- [ ] **Partial failure:** Fast path reports all failing answers before modifying any content -- verify with a batch where answers 2 and 4 have bad IDs
- [ ] **Existing tests:** All 234 existing tests still pass after adding the fast path -- verify by running full test suite
- [ ] **Multi-run cells:** Fast path extracts formatting from the correct run in multi-run cells -- verify with bold-label + normal-placeholder fixture
- [ ] **Newline handling:** Fast path converts `\n` to `<w:br/>` elements -- verify with multi-line answer text
- [ ] **verify_output compatibility:** verify_output produces identical results for documents filled via either path -- verify with same answer set written via both paths
- [ ] **Per-item path still works:** `build_insertion_xml` and per-answer `write_answers` continue to function identically -- verify existing pipeline tests pass unchanged

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Formatting divergence between paths | MEDIUM | 1. Add comparison test (both paths, same input). 2. Find divergence. 3. Fix fast path to match old path. 4. Re-run fixture tests. |
| Structured answer mishandled in batch | LOW | 1. Add answer_type validation to batch entry point. 2. Return error for structured. 3. Add test. |
| Document parsed multiple times | LOW | 1. Refactor to single-parse architecture. 2. Profile before/after with 50-answer batch. 3. Verify 3x+ speedup. |
| xml:space dropped for edge cases | LOW | 1. Add test cases for space edge cases. 2. Fix `build_run_xml` or fast-path builder. 3. Verify verify_output passes. |
| verify_output text extraction mismatch | MEDIUM | 1. Normalize whitespace in `_extract_text()`. 2. Handle `<w:br/>` as newline. 3. Collapse double spaces. 4. Re-run all verification tests. |
| Agent loses inspect-before-write capability | LOW | 1. Add per-answer `insertion_xml_used` to batch response. 2. Document behavioral change. |
| Partial failure destroys successful insertions | MEDIUM | 1. Add validate-all-before-apply-any pattern. 2. Return per-answer status. 3. Add skip-on-error option. |
| Multi-run formatting picks wrong run | MEDIUM | 1. Change heuristic to prefer last run or placeholder run. 2. Add multi-run fixture tests. 3. Document heuristic. |
| Stale element IDs from modified document | LOW | 1. Always re-parse document in write_answers (already the case). 2. Verify XPath resolves before applying. 3. Return "not found" error per answer. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Formatting divergence (#1) | Phase 1: Implementation | Comparison test: both paths produce identical insertion XML for all fixture answers |
| Structured answer conflation (#2) | Phase 1: API design | Test: batch call with structured answer returns error, per-item path still works |
| Double document parsing (#3) | Phase 1: Implementation | Profile: batch write for 50 answers completes in < 1 second |
| xml:space edge cases (#4) | Phase 1: XML builder | Tests: space-only text, newlines, tabs, empty string all produce correct OOXML |
| verify_output text mismatch (#5) | Phase 1: Verification | Test: same answer set written via both paths produces identical verify_output results |
| Lost inspect-before-write (#6) | Phase 1: API design | Test: batch response includes `insertion_xml_used` for each answer |
| Partial failure (#7) | Phase 1: Error handling | Test: batch with 2 bad IDs out of 10 returns all 2 errors without modifying document |
| No target_context_xml for compact agents (#8) | Phase 1: API design | Test: batch write accepts element_id + answer_text, produces correct document |
| Multi-run formatting (#9) | Phase 1: Formatting extraction | Test: cell with bold label + normal placeholder, answer inherits normal formatting |

## Sources

- [OOXML Style Hierarchy](https://c-rex.net/samples/ooxml/e1/Part4/OOXML_P4_DOCX_Style_topic_ID0ECYKT.html) -- resolution order for formatting properties
- [OOXML Style Inheritance](https://c-rex.net/samples/ooxml/e1/Part4/OOXML_P4_DOCX_Style_topic_ID0EITKT.html) -- basedOn chains and toggle property behavior
- [OOXML Document Defaults](https://c-rex.net/samples/ooxml/e1/part4/OOXML_P4_DOCX_docDefaults_topic_ID0EQQTT.html) -- docDefaults applied first in hierarchy
- [OpenXML Style Inheritance Challenges](http://james.newtonking.com/archive/2008/01/09/openxml-document-style-inheritance) -- developer experience with formatting edge cases
- [OOXML rPr Specification](https://c-rex.net/samples/ooxml/e1/part4/OOXML_P4_DOCX_rPr_topic_ID0EEHTO.html) -- run properties element definition
- [xml:space="preserve" in WordML](http://www.jenitennison.com/2007/07/13/things-that-make-me-scream-xmlspacepreserve-in-wordml.html) -- whitespace handling edge cases in OOXML
- [OOXML Styles Overview](http://officeopenxml.com/WPstyles.php) -- comprehensive style system documentation
- [MCP Batching Removed in 2025-06-18](https://www.speakeasy.com/mcp/release-notes) -- JSON-RPC batching removed from protocol; optimization must happen at tool level
- [Backward Compatibility in APIs](https://google.aip.dev/180) -- Google's API improvement proposal on backward compatibility principles
- [Zalando REST API Compatibility Guidelines](https://github.com/zalando/restful-api-guidelines/blob/main/chapters/compatibility.adoc) -- adding fields and maintaining backward compat
- Codebase analysis: `src/xml_formatting.py`, `src/handlers/word_writer.py`, `src/handlers/word_verifier.py`, `src/handlers/word_indexer.py`, `src/handlers/word.py`, `src/tools_extract.py`, `src/models.py`

---
*Pitfalls research for: Batch/Fast-Path Operations for MCP Form Filler Round-Trip Reduction*
*Researched: 2026-02-17*
