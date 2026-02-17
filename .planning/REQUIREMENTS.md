# Requirements: Form Filler MCP Server

**Defined:** 2026-02-17
**Core Value:** Agents fill forms correctly and fast -- fewest possible round-trips

## v2.1 Requirements

Requirements for the Gemini Consolidation milestone. Fixes cross-platform agent ergonomics issues.

### Ergonomics

- [ ] **ERG-01**: `extract_structure_compact` response includes `file_path` when provided as input
- [ ] **ERG-02**: `write_answers` error for missing file input says "Missing file_path -- this is the path you passed to extract_structure_compact"
- [ ] **ERG-03**: `xpath` is optional in `AnswerPayload` when `answer_text` is provided -- server resolves from `pair_id` via id_to_xpath re-extraction
- [ ] **ERG-04**: `mode` defaults to `replace_content` when `answer_text` is provided and mode is omitted
- [ ] **ERG-05**: When both `xpath` and `pair_id` are provided, server cross-checks and warns on mismatch (pair_id is authority)

### Tolerance

- [ ] **TOL-01**: `answer_text="SKIP"` recognized as intentional skip -- no write, status="skipped" in response
- [ ] **TOL-02**: Skipped fields reported in `write_answers` response summary with count

### Verification

- [ ] **VER-01**: `verify_output` accepts `pair_id` without `xpath` -- resolves from pair_id via re-extraction
- [ ] **VER-02**: `verify_output` cross-checks xpath against pair_id resolution when both provided

### Pipeline & Documentation

- [ ] **PIPE-01**: CLAUDE.md pipeline includes style review step between write and verify
- [ ] **PIPE-02**: CLAUDE.md documents SKIP convention for intentionally blank fields
- [ ] **PIPE-03**: All tool docstrings updated with new parameters and conventions
- [ ] **PIPE-04**: CLAUDE.md agent guidance documents simplified fast-path parameter set

### Quality Assurance

- [ ] **QA-01**: All 281 existing tests pass after changes
- [ ] **QA-02**: New tests for pair_id->xpath resolution in write_answers
- [ ] **QA-03**: New tests for SKIP handling
- [ ] **QA-04**: New tests for verify_output with pair_id only

## v2.0 Requirements (Completed)

### Fast Path

- [x] **FAST-01**: Server builds insertion OOXML from plain text internally when `answer_text` is provided
- [x] **FAST-02**: Fast path inherits formatting identically to build_insertion_xml
- [x] **FAST-03**: All three insertion modes work with answer_text
- [x] **FAST-04**: Validation rejects answers with neither answer_text nor insertion_xml
- [x] **FAST-05**: `extract_formatting_from_element()` exposed as public function

### Backward Compatibility

- [x] **COMPAT-01**: Existing agents using insertion_xml continue working unchanged
- [x] **COMPAT-02**: Mixed answer_text and insertion_xml in same call works

## Future Requirements

- **PERF-01**: Per-answer status reporting in write_answers response
- **PERF-02**: Combined write_and_verify tool (saves 1 round-trip)
- **PERF-04**: Formatting override hints in answer_text payloads

## Out of Scope

| Feature | Reason |
|---------|--------|
| Remove build_insertion_xml tool | Breaking change; needed for structured answers |
| Server-side AI for style fixes | Server is deterministic only; agent IS the AI |
| Persistent state / session caching | Stateless design is core constraint |
| Auto-detect question vs answer cells | Already handled by role indicators in extract |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ERG-01 | Phase 9 | Pending |
| ERG-02 | Phase 9 | Pending |
| ERG-03 | Phase 8 | Pending |
| ERG-04 | Phase 8 | Pending |
| ERG-05 | Phase 8 | Pending |
| TOL-01 | Phase 9 | Pending |
| TOL-02 | Phase 9 | Pending |
| VER-01 | Phase 10 | Pending |
| VER-02 | Phase 10 | Pending |
| PIPE-01 | Phase 11 | Pending |
| PIPE-02 | Phase 11 | Pending |
| PIPE-03 | Phase 11 | Pending |
| PIPE-04 | Phase 11 | Pending |
| QA-01 | Phase 11 | Pending |
| QA-02 | Phase 11 | Pending |
| QA-03 | Phase 11 | Pending |
| QA-04 | Phase 11 | Pending |

**Coverage:**
- v2.1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after v2.1 roadmap creation*
