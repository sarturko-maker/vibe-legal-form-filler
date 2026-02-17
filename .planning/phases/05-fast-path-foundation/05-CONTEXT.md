# Phase 5: Fast Path Foundation - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Define the API contract for `answer_text` on `AnswerPayload`, expose `extract_formatting_from_element()` as a public function, and add validation that enforces correct usage. No changes to the write path yet — Phase 6 implements the actual fast path.

</domain>

<decisions>
## Implementation Decisions

### Field precedence rules
- When an agent provides BOTH `answer_text` and `insertion_xml` on the same answer object, **reject with error** — do not silently prefer one field
- Error message should suggest which field to use: "Use `answer_text` for plain text answers, `insertion_xml` for structured OOXML. Don't provide both."
- In a mixed-mode `write_answers` call (some answers use `answer_text`, others use `insertion_xml`), validation is per-answer
- However, if ANY answer is invalid, **reject the entire batch before writing** — no partial writes
- Error lists ALL invalid answers, not just the first one

### "Provided" definition
- Empty string (`""`) = **not provided**
- Whitespace-only string (`"   "`) = **not provided** (strip before checking)
- Same strip-check logic applies to both `answer_text` and `insertion_xml` — consistent behavior
- Pydantic model defaults changed from empty string to **`None`** — `None` means "not provided", makes intent unambiguous
- Validation rule: exactly one of `answer_text` or `insertion_xml` must be non-None and non-empty after stripping

### Error response design
- Error messages list ALL invalid answers in the batch, not just the first
- Each invalid answer referenced by **both pair_id and position index**: e.g. "Answer 'q3' (index 2): ..."
- Distinct error messages for the two failure modes:
  - Neither provided: "Neither `answer_text` nor `insertion_xml` provided. Use `answer_text` for plain text answers, `insertion_xml` for structured OOXML."
  - Both provided: "Both `answer_text` and `insertion_xml` provided — use one, not both. Use `answer_text` for plain text, `insertion_xml` for structured OOXML."
- Guidance included in error messages to help agents self-correct

### Claude's Discretion
- Exact Pydantic validator implementation (model_validator vs field_validator)
- `extract_formatting_from_element()` return type and internal structure
- Test organization and fixture design
- How to structure the validation error aggregation

</decisions>

<specifics>
## Specific Ideas

- Error messages should read naturally to an AI agent — they'll appear in the agent's conversation context and need to be actionable
- The `None` default is important: agents that omit a field get `None`, agents that deliberately send `""` also get treated as "not provided" (consistent, no foot-guns)
- Batch rejection (all-or-nothing) prevents partial document corruption — agent retries the whole call after fixing invalid answers

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-fast-path-foundation*
*Context gathered: 2026-02-17*
