# Phase 11: Documentation & QA - Research

**Researched:** 2026-02-17
**Domain:** Documentation updates, test coverage validation, docstring maintenance
**Confidence:** HIGH

## Summary

Phase 11 is the final phase of v2.1 Gemini Consolidation. Its scope is documentation and quality assurance -- no new code behavior. Phases 8-10 implemented all functional changes (pair_id resolution, SKIP convention, mode defaults, verify_output parity). Phase 11 must: (1) update CLAUDE.md to reflect the simplified API, (2) update tool docstrings, and (3) verify/augment test coverage.

The codebase is in good shape. All 311 tests pass. Phases 8-10 already added 30 tests covering pair_id resolution (QA-02), SKIP handling (QA-03), and verify_output with pair_id (QA-04). The primary work is CLAUDE.md restructuring and docstring updates -- the QA requirements are largely satisfied by existing tests, though Phase 11 must formally validate this and fill any gaps.

**Primary recommendation:** Focus on CLAUDE.md edits (pipeline step, SKIP docs, agent guidance rewrite) and tool docstring updates. Run the full test suite to confirm QA-01. Review existing test coverage against QA-02/03/04 and add any edge cases not yet covered.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | CLAUDE.md pipeline includes style review step between write and verify | CLAUDE.md pipeline section (lines 44-99) needs a new "STEP 5.5: STYLE REVIEW" between current STEP 5 (WRITE) and STEP 6 (VERIFY). See Architecture Patterns for exact placement. |
| PIPE-02 | CLAUDE.md documents SKIP convention for intentionally blank fields | No SKIP documentation exists in CLAUDE.md. Add to pipeline section, write_answers tool description, and agent guidance. See Code Examples for content. |
| PIPE-03 | All tool docstrings updated with new parameters and conventions | `tools_write.py::write_answers` docstring is already updated (pair_id, answer_text, optional xpath/mode). `tools_write.py::verify_output` docstring is already updated (optional xpath). `tools_extract.py` tools unchanged. Minor additions needed for SKIP in write_answers docstring. |
| PIPE-04 | CLAUDE.md agent guidance documents simplified fast-path parameter set | Current agent guidance (lines 111-141) still references old workflow (step 7: build_insertion_xml). Must add simplified fast-path guidance showing pair_id + answer_text only. |
| QA-01 | All 281 existing tests pass after changes | 311 tests currently pass (281 pre-v2.1 + 30 from phases 8-10). Run `pytest tests/` to confirm. |
| QA-02 | New tests for pair_id->xpath resolution in write_answers | Already exists: `test_resolution.py::TestPairIdOnlyWrite` (6 tests) and `test_pair_id_resolver.py` (9 tests). |
| QA-03 | New tests for SKIP handling | Already exists: `test_ergonomics.py::TestSkipConvention` (3 tests) and `test_ergonomics.py::TestWriteAnswersSummary` (3 tests, including dry_run SKIP). |
| QA-04 | New tests for verify_output with pair_id only | Already exists: `test_resolution.py::TestPairIdOnlyVerify` (5 tests). |
</phase_requirements>

## Standard Stack

### Core

No new libraries needed. Phase 11 is documentation-only.

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| pytest | existing | Test runner | Run full suite to validate QA-01 |

### Files to Modify

| File | What Changes | Why |
|------|-------------|-----|
| `CLAUDE.md` | Pipeline step addition, SKIP docs, agent guidance rewrite | PIPE-01, PIPE-02, PIPE-04 |
| `src/tools_write.py` | Minor docstring additions (SKIP convention mention) | PIPE-03 |
| `src/tools_extract.py` | No changes needed -- docstrings already current | PIPE-03 (verification only) |

## Architecture Patterns

### CLAUDE.md Pipeline Changes (PIPE-01)

The current pipeline has 6 steps. A "STYLE REVIEW" step must be inserted between STEP 5 (WRITE ANSWERS) and STEP 6 (VERIFY OUTPUT). This is a human/agent review step, not a new MCP tool.

**Current pipeline:**
```
STEP 1: EXTRACT STRUCTURE
STEP 2: VALIDATE LOCATIONS
STEP 3: BUILD INSERTION XML
STEP 4: DRY RUN
STEP 5: WRITE ANSWERS
STEP 6: VERIFY OUTPUT
```

**Updated pipeline (renumber STEP 6 to STEP 7):**
```
STEP 1: EXTRACT STRUCTURE
STEP 2: VALIDATE LOCATIONS
STEP 3: BUILD INSERTION XML
STEP 4: DRY RUN
STEP 5: WRITE ANSWERS
STEP 6: STYLE REVIEW (agent-side — not an MCP tool)
  Action: Agent opens the filled document and reviews formatting/style.
          Check font consistency, alignment, spacing, and visual appearance.
          This is a manual/agent review step — no MCP tool call needed.
STEP 7: VERIFY OUTPUT (MCP tool — deterministic)
```

### CLAUDE.md Agent Guidance (PIPE-04)

The agent orchestration section (lines 111-141) currently shows the old 11-step workflow that includes `build_insertion_xml` (step 7) and `validate_locations` (step 5) as mandatory steps. The v2.1 fast path makes these optional. The updated guidance should show:

1. The **simplified fast path** (pair_id + answer_text only, 5 tool calls)
2. The **full path** (existing workflow, for agents that need insertion_xml or structured answers)

**Simplified fast-path orchestration:**
```
1. extract_structure_compact(file_path="form.docx")
2. Agent identifies Q/A pairs, generates answers (pair_id + answer_text)
   - Use SKIP for intentionally blank fields (signatures, dates)
3. write_answers(file_path="form.docx", answers=[{pair_id, answer_text}], dry_run=True)
4. write_answers(file_path="form.docx", answers=[{pair_id, answer_text}], output_file_path="filled.docx")
5. verify_output(file_path="filled.docx", expected_answers=[{pair_id, expected_text}])
```

No validate_locations, no build_insertion_xml, no xpath, no mode needed.

### SKIP Convention Documentation (PIPE-02)

The SKIP convention is implemented but not documented in CLAUDE.md. It needs to appear in three places:

1. **Pipeline section** -- mention in WRITE ANSWERS step description
2. **write_answers tool description** -- document `answer_text="SKIP"` behavior
3. **Agent guidance** -- explain when to use SKIP (signatures, dates, fields the user will fill manually)

### Docstring Audit (PIPE-03)

Current state of tool docstrings:

| Tool | File | Status | Notes |
|------|------|--------|-------|
| `write_answers` | `tools_write.py:98` | Mostly current | Already mentions pair_id, answer_text, optional xpath/mode. Add SKIP mention. |
| `verify_output` | `tools_write.py:205` | Current | Already mentions optional xpath, pair_id resolution. |
| `extract_structure_compact` | `tools_extract.py:51` | Unchanged | No v2.1 changes needed (file_path echo is in the tool implementation, not the docstring). |
| `validate_locations` | `tools_extract.py:123` | Unchanged | No v2.1 changes needed. |
| `build_insertion_xml` | `tools_extract.py:158` | Unchanged | No v2.1 changes needed. |
| `list_form_fields` | `tools_extract.py:177` | Unchanged | No v2.1 changes needed. |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test gap analysis | Manually trace requirements to tests | Run existing test suite, map test names to requirement IDs | Tests already exist from phases 8-10; adding duplicates wastes effort |
| New MCP tools for style review | A `style_review` MCP tool | Document it as an agent-side step | Server is deterministic only; style review is subjective/AI-driven |

## Common Pitfalls

### Pitfall 1: Over-writing existing v2.1 documentation
**What goes wrong:** CLAUDE.md's write_answers and verify_output tool descriptions already partially reflect v2.1 changes (they mention optional xpath). Overwriting them completely could lose existing accurate content.
**Why it happens:** Phase 11 writer doesn't realize phases 8-10 already updated some documentation inline.
**How to avoid:** Read current CLAUDE.md carefully before making edits. Preserve existing v2.1 content, add missing pieces only (SKIP, style review step, fast-path guidance).
**Warning signs:** Diff shows large deletions of recently-added content.

### Pitfall 2: Renumbering chaos in CLAUDE.md
**What goes wrong:** Inserting a new step between STEP 5 and STEP 6 requires renumbering STEP 6 to STEP 7. All cross-references to "STEP 6" throughout CLAUDE.md must be updated.
**Why it happens:** The pipeline step numbers are referenced in multiple places (pipeline section, agent guidance, tool descriptions).
**How to avoid:** Search for all occurrences of "STEP 6" and "step 6" in CLAUDE.md and update consistently. Also update the agent guidance numbering.
**Warning signs:** Agent guidance says "verify" is step 10 but pipeline says step 7.

### Pitfall 3: Confusing "existing tests" count
**What goes wrong:** Requirements say "281 existing tests" but there are now 311. Phase 11 might think 30 tests are missing.
**Why it happens:** The 281 count was from before phases 8-10 added 30 new tests.
**How to avoid:** QA-01 success criterion is "all existing tests pass" -- the count (281 or 311) is less important than the pass rate. Run `pytest tests/ -q` and confirm 0 failures.
**Warning signs:** Trying to add tests to reach 281 when they already exceed it.

### Pitfall 4: Duplicating test coverage
**What goes wrong:** Phase 11 adds new test files for QA-02/03/04 that duplicate tests already in test_resolution.py and test_ergonomics.py.
**Why it happens:** Not realizing phases 8-10 already created these tests as part of TDD.
**How to avoid:** Check existing test files first. QA-02 = test_resolution.py::TestPairIdOnlyWrite + test_pair_id_resolver.py. QA-03 = test_ergonomics.py::TestSkipConvention + TestWriteAnswersSummary. QA-04 = test_resolution.py::TestPairIdOnlyVerify. Only add tests for gaps.
**Warning signs:** Test count jumps by 15+ with all-duplicate names.

## Code Examples

### CLAUDE.md: SKIP Convention Documentation

Add to write_answers tool description after the answer format examples:
```markdown
**SKIP convention:** Set `answer_text` to `"SKIP"` (case-insensitive) for fields
that should be left intentionally blank — signatures, dates the signer fills in,
or fields the user wants to complete manually. SKIP answers are not written to
the document. The response summary reports the count of skipped fields.
```

### CLAUDE.md: Simplified Fast-Path Agent Guidance

```markdown
### Simplified Pipeline (v2.1 fast path)

For plain-text answers, agents need only `pair_id` and `answer_text` — no xpath,
no mode, no build_insertion_xml call. The server resolves everything automatically.

```
1. Agent calls extract_structure_compact(file_path="form.docx")
   → gets compact_text with element IDs and role indicators
2. Agent identifies Q/A pairs from compact_text
   → for each [answer] cell, note the pair_id (e.g., T1-R2-C2)
   → generate the answer text from knowledge + user instructions
   → use "SKIP" for fields the user will fill manually (signatures, dates)
3. Agent calls write_answers(file_path="form.docx", answers=[
       {"pair_id": "T1-R2-C2", "answer_text": "Acme Corp"},
       {"pair_id": "T1-R3-C2", "answer_text": "SKIP"},
   ], dry_run=True) → preview
4. Agent calls write_answers(file_path="form.docx", answers=[...],
       output_file_path="filled.docx") → filled document
5. Agent reviews style/formatting of filled document
6. Agent calls verify_output(file_path="filled.docx",
       expected_answers=[{"pair_id": "T1-R2-C2", "expected_text": "Acme Corp"}])
   → confirms all answers written correctly
```

No validate_locations, no build_insertion_xml, no xpath bookkeeping needed.
The full pipeline (with validate_locations and build_insertion_xml) remains
available for structured OOXML answers or agents that need snippet matching.
```

### CLAUDE.md: Style Review Step

```markdown
STEP 6: STYLE REVIEW (agent-side — not an MCP tool)
  Action: Agent opens or re-extracts the filled document and reviews
          formatting consistency. Check that inserted text matches the
          document's existing font, size, and style. This is a visual
          review step — no MCP tool call needed.
  Note:   This step is recommended but optional. The server inherits
          formatting from target elements during write, so most answers
          will match. Review catches edge cases (e.g., bold headers
          that should not be bold in answers).
```

### write_answers Docstring Addition

Add SKIP mention to existing docstring:
```python
"""Write all answers into the document and return the completed file bytes.

    ...existing content...

    SKIP convention: Set answer_text to "SKIP" (case-insensitive) for fields
    that should remain blank. SKIP answers are excluded from writing. The
    response summary reports written and skipped counts.
"""
```

## State of the Art

| Old Approach (v2.0) | Current Approach (v2.1) | Impact |
|---------------------|------------------------|--------|
| Agent provides xpath + insertion_xml + mode | Agent provides pair_id + answer_text only | 3 fewer fields per answer, no build_insertion_xml call |
| Agent must track xpaths from extraction | Server re-extracts and resolves pair_id to xpath | Stateless; no bookkeeping burden on agent |
| No way to skip fields | answer_text="SKIP" convention | Agent explicitly marks intentional blanks |
| verify_output requires xpath | verify_output accepts pair_id only | Same simplified interface for both write and verify |
| 5-step agent workflow minimum | 3-step agent workflow (extract + write + verify) | Fewer round-trips, simpler agent prompts |

## QA Assessment

### Test Coverage Mapping

| Requirement | Test File | Test Count | Status |
|-------------|-----------|------------|--------|
| QA-01 (all tests pass) | `tests/` (full suite) | 311 | Pass -- run `pytest tests/ -q` |
| QA-02 (pair_id->xpath write) | `test_resolution.py::TestPairIdOnlyWrite` | 6 | Exist and pass |
| QA-02 (pair_id resolver unit) | `test_pair_id_resolver.py` | 9 | Exist and pass |
| QA-03 (SKIP handling) | `test_ergonomics.py::TestSkipConvention` | 3 | Exist and pass |
| QA-03 (SKIP summary) | `test_ergonomics.py::TestWriteAnswersSummary` | 3 | Exist and pass |
| QA-04 (verify pair_id only) | `test_resolution.py::TestPairIdOnlyVerify` | 5 | Exist and pass |

### Potential Test Gaps

After reviewing existing tests, the following edge cases are potentially uncovered:

1. **SKIP in verify_output expected_answers** -- what happens if an agent passes expected_text="SKIP" to verify? (Likely "mismatched" since the cell is empty, but no test confirms this.)
2. **Multiple pair_ids resolved in single write_answers call** -- test_resolution only tests 1 answer at a time for pair_id-only Word writes. A multi-answer test would be stronger.
3. **PDF pair_id-only verify_output** -- test_resolution.py only tests Word and Excel for pair_id-only verify, not PDF.

These are LOW priority gaps -- the core paths are well tested. The planner should decide whether to add these.

## Open Questions

1. **What does "style review step" mean concretely?**
   - What we know: The success criterion says "CLAUDE.md pipeline includes style review step between write and verify"
   - What's unclear: Whether this is purely a documentation addition or implies adding a new MCP tool
   - Recommendation: Document it as an agent-side review step (not a new tool). The server is deterministic-only per design constraints. The style review is subjective and belongs to the agent.

2. **Should the pipeline step numbers be renumbered?**
   - What we know: Inserting a step between 5 and 6 requires renumbering
   - Recommendation: Renumber STEP 6 to STEP 7. Update all references in CLAUDE.md consistently.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `CLAUDE.md` (660 lines) -- full current state of documentation
- Direct code inspection of `src/tools_write.py` -- current docstrings for write_answers and verify_output
- Direct code inspection of `src/tools_extract.py` -- current docstrings for extract tools
- Direct code inspection of `src/models.py` -- AnswerPayload, ExpectedAnswer models
- Direct code inspection of `src/pair_id_resolver.py` -- resolution logic
- Direct code inspection of `src/tool_errors.py` -- validation and payload construction
- Test suite execution: `pytest tests/ -q` -- 311 tests, all passing
- Direct inspection of `test_resolution.py`, `test_ergonomics.py`, `test_pair_id_resolver.py` -- existing v2.1 test coverage

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` -- formal requirement definitions for PIPE-01 through QA-04
- `.planning/ROADMAP.md` -- phase dependencies and success criteria

## Metadata

**Confidence breakdown:**
- Documentation changes: HIGH -- direct inspection of current CLAUDE.md shows exactly what's missing
- Docstring updates: HIGH -- tools_write.py docstrings are mostly current, minor SKIP addition needed
- Test coverage: HIGH -- all test files inspected, tests run successfully, coverage mapped to requirements
- Pipeline step numbering: HIGH -- straightforward insertion with consistent renumbering

**Research date:** 2026-02-17
**Valid until:** No expiration (documentation phase, not technology-dependent)
