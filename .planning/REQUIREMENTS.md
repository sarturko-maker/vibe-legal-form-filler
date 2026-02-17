# Requirements: Form Filler MCP Server

**Defined:** 2026-02-17
**Core Value:** Agents fill forms correctly and fast — fewest possible round-trips

## v2.0 Requirements

Requirements for the performance optimization milestone. Each maps to roadmap phases.

### Fast Path

- [ ] **FAST-01**: Server builds insertion OOXML from plain text internally when `answer_text` is provided in write_answers
- [ ] **FAST-02**: Fast path inherits formatting (font, size, bold, italic, color) from the target element identically to build_insertion_xml
- [ ] **FAST-03**: All three insertion modes (replace_content, append, replace_placeholder) work with answer_text
- [ ] **FAST-04**: Validation rejects answers with neither answer_text nor insertion_xml, with a clear error message
- [ ] **FAST-05**: `extract_formatting_from_element()` exposed as public function in xml_formatting.py

### Backward Compatibility

- [ ] **COMPAT-01**: Existing agents using insertion_xml continue working with zero changes
- [ ] **COMPAT-02**: Mixed answer_text and insertion_xml answers work in the same write_answers call

### Quality Assurance

- [ ] **QA-01**: Parity test proves fast path produces byte-identical output to old path on fixture data
- [ ] **QA-02**: Edge-case tests cover leading/trailing spaces, special XML characters, empty strings
- [ ] **QA-03**: All 234 existing tests still pass after changes

### Documentation

- [ ] **DOCS-01**: CLAUDE.md updated with new pipeline showing answer_text as preferred path for plain text
- [ ] **DOCS-02**: Agent guidance explains when to use answer_text vs insertion_xml

## Future Requirements

Deferred to later milestones. Tracked but not in current roadmap.

### Performance Extras

- **PERF-01**: Per-answer status reporting in write_answers response (behavior change from fail-fast)
- **PERF-02**: Combined write_and_verify tool (saves 1 additional round-trip)
- **PERF-03**: Multi-line answer_text handling with `<w:br/>` elements
- **PERF-04**: Formatting override hints in answer_text payloads

## Out of Scope

| Feature | Reason |
|---------|--------|
| Remove build_insertion_xml tool | Breaking change; needed for structured answers |
| New batch_build_insertion_xml tool | Still requires extra round-trip; fast path is strictly better |
| Heuristic XML detection (sniff content) | Fragile; explicit answer_text field is unambiguous |
| Async/parallel XML building | 26ms total for 30 answers; GIL prevents parallelism anyway |
| Template caching for formatting | Each target has different formatting; no cache hits |
| Unified answer schema across file types | Larger refactor; Excel/PDF already accept plain text |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FAST-01 | — | Pending |
| FAST-02 | — | Pending |
| FAST-03 | — | Pending |
| FAST-04 | — | Pending |
| FAST-05 | — | Pending |
| COMPAT-01 | — | Pending |
| COMPAT-02 | — | Pending |
| QA-01 | — | Pending |
| QA-02 | — | Pending |
| QA-03 | — | Pending |
| DOCS-01 | — | Pending |
| DOCS-02 | — | Pending |

**Coverage:**
- v2.0 requirements: 12 total
- Mapped to phases: 0
- Unmapped: 12

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17 after initial definition*
