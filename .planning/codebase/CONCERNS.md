# Codebase Concerns

**Analysis Date:** 2026-02-16

## Tech Debt

**Large XML Document Processing:**
- Issue: Word documents with very large tables (100+ rows) or deeply nested structures can cause performance degradation in extraction and validation loops. The `xml_snippet_matching.py` uses `.iter()` which traverses the entire tree recursively.
- Files: `src/handlers/word_indexer.py:46-79`, `src/xml_snippet_matching.py:158`, `src/handlers/word_fields.py:58-61`
- Impact: Extraction time scales linearly with document size. For documents >10MB or with >1000 table rows, extraction and validation steps may become noticeably slower.
- Fix approach: Add optional tree depth limiting or implement lazy iteration for very large documents. Consider caching XPath results if the same document is processed multiple times.

**Dependency on Stable openpyxl Release Cadence:**
- Issue: `openpyxl` (3.1.5) has a slow release cadence. New versions are infrequent (~6 months apart). Security vulnerabilities or compatibility issues with future Python versions would require waiting for a release or pinning to an older version.
- Files: `requirements.txt:22`, `pyproject.toml:14`
- Impact: Security patches may lag 3-6 months behind vulnerability discovery. For organizations with aggressive security policies, this is a risk.
- Fix approach: Monitor openpyxl's GitHub for critical issues. Maintain an alternate fork or vendored copy if security patches are needed urgently.

**PyMuPDF (fitz) Licensing Mixed AGPL/Commercial:**
- Issue: PyMuPDF is dual-licensed under AGPL-3.0 and a commercial license. The installed version includes AGPL code, which is compatible with this project's AGPL-3.0 license. However, any organization running this server that wants to avoid AGPL copyleft constraints would need to negotiate a commercial PyMuPDF license or replace the PDF handler with an AGPL-compatible alternative.
- Files: `src/handlers/pdf.py`, `src/handlers/pdf_*.py`
- Impact: Limits distribution and use in proprietary codebases unless commercial PyMuPDF licenses are obtained for all users.
- Fix approach: Document licensing clearly. For organizations avoiding AGPL, provide a guide to replace PyMuPDF with `pypdf` or similar LGPL/MIT alternatives (though functionality will be reduced for PDF writing).

**No Bundled Dependency Hashing:**
- Issue: `requirements.txt` pins exact versions but does not include hash verification (`--hash` flag). A compromised package on PyPI with the same version number would not be detected.
- Files: `requirements.txt`
- Impact: Low-likelihood but high-impact supply chain attack vector.
- Fix approach: Generate hashes using `pip-compile --generate-hashes` and verify on install. For CI/CD pipelines, use `pip install --require-hashes`.

## Known Bugs

None detected during current audit. The SELF_TEST_REPORT.md (2026-02-12) identified and fixed 1 test bug (namespace prefix assertion) but no server-side bugs. All 207 tests pass.

## Security Considerations

**Formula Injection Risk (Mitigated):**
- Risk: Excel formulas starting with `=`, `+`, `-`, or `@` can execute arbitrary code when a spreadsheet is opened. A malicious calling agent could inject formulas.
- Files: `src/handlers/excel_writer.py:49-57`
- Current mitigation: Excel writer forces `cell.data_type = "s"` for any value starting with formula prefixes, ensuring the value is stored as a string literal.
- Recommendations: Maintain this defense. Add logging when a formula-like value is detected and coerced to string (for audit purposes). Test with actual Excel to confirm formulas are not interpreted.

**XML Injection via Structured Answer Path (By Design):**
- Risk: The `build_insertion_xml()` tool accepts AI-generated OOXML snippets for the `structured` answer type. A malicious agent could inject hidden text via `<w:vanish/>` elements or other formatting tricks.
- Files: `src/xml_validation.py:44`, `src/tools_extract.py:151-188`
- Current mitigation: The `structured` path is explicitly marked as "for advanced agents that need custom XML." The trust boundary is the calling agent, which already controls all document content. The `plain_text` path (the common case) does not allow agent-controlled XML.
- Recommendations: Accept as designed. Document that the `structured` path trusts the calling agent fully. Encourage agents to use `plain_text` unless they need advanced control.

**XPath Injection Prevention (In Place):**
- Risk: If an agent passes an untrusted XPath expression to `write_answers`, it could theoretically execute XPath functions or traversal logic.
- Files: `src/handlers/word_writer.py:133-140`
- Current mitigation: `_validate_xpath()` uses a strict regex whitelist (`_XPATH_SAFE_RE`) that only allows positional predicates on known OOXML element names. No function calls or complex logic allowed.
- Recommendations: Good. Keep the whitelist maintained as new OOXML elements are added to the supported list.

**Path Traversal Prevention (In Place):**
- Risk: If an agent passes a malicious `file_path` or `output_file_path`, it could read/write files outside the intended directory.
- Files: `src/validators.py:79-96`
- Current mitigation: `validate_path_safe()` resolves symlinks via `Path.resolve()`, blocks null bytes, and blocks access to `/dev/`, `/proc/`, `/sys/`. This is sufficient for local use.
- Recommendations: Good. Consider adding optional allow-list functionality if the server is ever deployed in a multi-tenant environment.

**XXE Prevention Complete:**
- Risk: XML External Entity (XXE) attacks via DOCTYPE declarations or entity expansion.
- Files: All XML parsing sites in `src/handlers/`, `src/xml_snippet_matching.py`, `src/xml_formatting.py`, `src/xml_validation.py`
- Current mitigation: All 12 `etree.fromstring()` calls use `SECURE_PARSER`, which disables external entity resolution, DTD loading, and network access.
- Recommendations: Maintain. Audit any new XML parsing code to ensure `SECURE_PARSER` is used.

## Performance Bottlenecks

**PDF Text Context Extraction:**
- Problem: PDF indexer expands widget bounding boxes by fixed 200pt horizontal, 30pt vertical (`_CONTEXT_EXPAND = (-200, -30, 200, 30)`) to grab nearby text for context. For PDFs with dense text or large pages, this can extract 1000+ characters of irrelevant context per field.
- Files: `src/handlers/pdf_indexer.py:40, 97-107`
- Cause: Fixed expansion constant doesn't adapt to page size or text density.
- Improvement path: Make expansion configurable or adaptive based on page dimensions. Implement text clipping to limit context to ~200 chars of relevant text only.

**Large Table Verification:**
- Problem: `verify_output()` iterates all table cells (`body.iter(w:tc)`) to check for structural issues. For documents with 1000+ table cells, this is O(n).
- Files: `src/handlers/word_verifier.py:45-70`
- Cause: No early termination or indexing. Structural issues are checked even if content verification is not needed.
- Improvement path: Add a flag to skip structural checks for known-good documents. Cache structural analysis from extraction phase.

**Snippet Matching Ambiguity Resolution:**
- Problem: `find_snippet_in_body()` in `xml_snippet_matching.py:139-163` finds ALL matches for a snippet, then returns the list. If a snippet appears in 10 places, all 10 are returned as "ambiguous." For large documents with repeating patterns, this could be slow.
- Files: `src/xml_snippet_matching.py:158`
- Cause: Linear search through all body elements of the snippet's tag.
- Improvement path: Implement heuristic ranking (e.g., prefer matches near the end of the document, or closest to the last successful match). Add a `max_matches` parameter to return early.

**Base64 Decoding Full String:**
- Problem: `resolve_file_input()` validates the full base64 string length (`MAX_BASE64_LENGTH = 67MB`) before decoding. For very large documents, this means storing the entire encoded string in memory before any parsing.
- Files: `src/validators.py:235-240`
- Cause: Input validation is conservative to prevent out-of-memory conditions.
- Improvement path: Stream decode base64 in chunks, or use `io.BytesIO` with incremental decoding for file_bytes_b64 inputs.

## Fragile Areas

**Word Element Complexity Detection:**
- Files: `src/handlers/word_element_analysis.py:105-150`
- Why fragile: The `detect_complex()` function flags elements with nested tables, content controls, legacy form fields, or merged cells as "complex" and returns raw XML instead of compact text. The heuristics are conservative — almost any non-trivial table cell is marked complex. This can result in 20-30% of a real-world document being flagged as complex, reducing the usefulness of the compact extraction.
- Safe modification: Add unit tests for edge cases (deeply nested tables, mixed content controls). Document the heuristics clearly. Consider lowering the "complex" threshold for agents that can handle raw XML.
- Test coverage: `test_word_indexer.py` covers basic cases. No tests for extremely nested structures or edge case heuristics.

**Word Verifier Structural Validation:**
- Files: `src/handlers/word_verifier.py:42-71`
- Why fragile: The structural checks look for "bare `<w:r>` directly under `<w:tc>`" and "every `<w:tc>` has a `<w:p>`", but this assumes standard OOXML structure. Some generators (older Word versions, alternative tools) might produce slightly different structures that still render correctly in Word. The validator could reject valid documents.
- Safe modification: Add a permissive mode that only warns instead of failing on structural issues. Test against a wide range of real-world documents.
- Test coverage: `test_word_verifier.py` tests the happy path. No tests against documents from non-Microsoft tools or older Word versions.

**PDF Context Text Clipping:**
- Files: `src/handlers/pdf_indexer.py:97-107`
- Why fragile: Text context is extracted by expanding widget bounds and calling `page.get_text("text", clip=expanded_rect)`. For PDFs with unusual text layouts, rotated text, or multi-column content, the clipped rect may grab irrelevant text or miss relevant text entirely.
- Safe modification: Add a test PDF with multi-column layout and rotated text. Improve the context extraction to prefer nearest text (by distance) rather than all text in the expanded box.
- Test coverage: `test_pdf.py` tests simple single-column PDFs. No test for complex layouts.

**Excel Sheet Reference by Index:**
- Files: `src/handlers/excel_writer.py:84-89`, `src/handlers/excel_indexer.py`
- Why fragile: Sheets are accessed by 1-indexed number (S1, S2, ...). If a spreadsheet has hidden sheets or sheets are deleted/reordered, the S-R-C IDs become misaligned. No mechanism to detect or warn about this.
- Safe modification: Add a sheet UUID or content hash to the id_to_xpath mapping so shifts are detected. Implement sheet matching by name as a fallback.
- Test coverage: `test_excel.py` tests a fixed-sheet workbook. No test for deleted/hidden/reordered sheets.

## Scaling Limits

**Max File Size (50 MB Hard Limit):**
- Current capacity: 50 MB per document (`MAX_FILE_SIZE` in `validators.py`)
- Limit: Memory-based. Entire file is loaded into a BytesIO or unpacked from ZIP. No streaming.
- Scaling path: Implement streaming extraction for large files. For Word, parse `word/document.xml` without loading the entire ZIP into memory. For PDF, page-by-page iteration already implemented, but content extraction loads each page fully.
- Impact: Enterprise users with very large scanned documents (>50MB) cannot use the server.

**Max Answers Per Request (10,000):**
- Current capacity: 10,000 answers per `write_answers` call (`MAX_ANSWERS` in `validators.py`)
- Limit: Linear performance scaling. All answers are processed sequentially, one XPath match + XML insertion per answer.
- Scaling path: Implement batching with early termination. For 100,000 answers, split into 10 batches of 10,000. Or implement answer deduplication (if the same XPath appears multiple times, only apply once).
- Impact: Very large forms (100+ questions) require multiple MCP tool calls or external batching.

**XPath Lookup Complexity:**
- Current capacity: Lookup scales with document size. For each answer, `body.xpath()` searches the entire tree.
- Limit: O(n) per answer. For 1000 answers in a large document, this becomes O(n*1000).
- Scaling path: Build an XPath index at extraction time, cache it. For write_answers, look up the index instead of searching.
- Impact: Writing 1000 answers to a large document may take 10-20 seconds instead of 1-2 seconds.

## Dependencies at Risk

**openpyxl — Slow Release Cadence:**
- Risk: Version 3.1.5 (released ~6 months ago). No recent updates. No clear roadmap for Python 3.13+ support.
- Impact: If a critical security vulnerability is found, fix may take months. Compatibility with future Python versions uncertain.
- Migration plan: `openpyxl` is the de facto standard for Excel in Python. No easy replacement. Consider maintaining a vendored fork if security updates lag.

**PyMuPDF — Licensing Complexity:**
- Risk: Dual AGPL/commercial licensing. The AGPL requirement is compatible with this project, but any downstream proprietary use requires commercial licenses.
- Impact: Limits enterprise adoption.
- Migration plan: Switch to `pypdf` (pure Python, MIT) for basic PDF field filling, but accept reduced functionality (no text extraction for context, no widget property inspection). Or maintain commercial license agreements with users.

**lxml — Active but Tightly Coupled:**
- Risk: lxml is a C extension (libxml2 binding). Updates can sometimes introduce subtle XML parsing changes or compatibility issues.
- Impact: All 12 XML parsing sites depend on lxml's behavior. A breaking change in lxml could affect the entire pipeline.
- Migration plan: Monitor lxml releases closely. Test against multiple lxml versions in CI. Consider adding a vendored fallback using `xml.etree` if lxml becomes unmaintained (though performance would degrade).

**pydantic — Version 2.x Migration Complete:**
- Risk: Project requires `pydantic>=2.4.0`. This is a major version with breaking changes from 1.x. Transitive dependencies may still depend on pydantic 1.x, causing conflicts.
- Impact: Currently, no conflicts detected. But this is a fragile dependency boundary.
- Migration plan: Monitor for transitive pydantic 1.x dependencies. Test regularly with `pip check`.

## Missing Critical Features

**No Streaming or Chunked Processing:**
- Problem: For very large documents or high-frequency answer sets, the entire document is processed in a single request. No ability to process in chunks.
- Blocks: Customers with >50MB documents, or systems that need to write 100,000+ answers across many documents.
- Recommendation: Implement optional streaming for `extract_structure_compact` (return answers in pages). For write_answers, support resume-from-checkpoint to handle timeouts.

**No Concurrency or Request Queuing:**
- Problem: The MCP server is single-threaded (stdio protocol). Multiple concurrent requests will queue and block.
- Blocks: High-volume deployments (e.g., processing 100 forms/second). Each request must wait for the previous to complete.
- Recommendation: This is an architectural limitation of the MCP stdio protocol. Scaling requires running multiple server instances and load-balancing at the MCP client level.

**No Caching Between Requests:**
- Problem: Every request re-parses the document from scratch. If the same document is processed twice (extraction followed by write), the XML tree is parsed twice.
- Blocks: Agents that need to make multiple MCP calls against the same document incur redundant parsing overhead.
- Recommendation: Add optional in-memory caching with a document hash as the key. Invalidate cache when document bytes change.

**No Format Conversion (Word ↔ Excel ↔ PDF):**
- Problem: Answers written to a Word document cannot be exported as Excel or PDF without a separate tool.
- Blocks: Workflows that need to produce multiple output formats from a single set of answers.
- Recommendation: Out of scope for this project. Document that format conversion requires separate tools (pandoc, LibreOffice, etc.).

## Test Coverage Gaps

**Untested: Deeply Nested OOXML Structures:**
- What's not tested: Word documents with tables nested 5+ levels deep, or complex content controls with mixed formatting.
- Files: `src/handlers/word_indexer.py`, `src/handlers/word_element_analysis.py`
- Risk: Edge case in detection or indexing could silently produce incorrect IDs or miss content.
- Recommendation: Priority: Medium. Create a fixture with extremely nested structure and test extraction coverage.

**Untested: PDF Multi-Column Layouts:**
- What's not tested: PDFs with multi-column text, rotated text, or text boxes overlapping form fields.
- Files: `src/handlers/pdf_indexer.py:97-107`
- Risk: Context text extraction could grab irrelevant text, confusing agents identifying questions.
- Recommendation: Priority: Medium. Create a test PDF with complex layout and validate context extraction.

**Untested: Very Large File Edge Cases:**
- What's not tested: Documents near the 50MB limit, Word documents with 1000+ pages, Excel files with 100+ sheets.
- Files: `src/validators.py:32-35`
- Risk: Memory/performance issues not discovered until production.
- Recommendation: Priority: Low (tests would be resource-intensive). Add documentation of tested limits instead.

**Untested: Malformed ZIP Archives:**
- What's not tested: .docx/.xlsx files with corrupted ZIP headers, missing required XML files, or truncated archives.
- Files: `src/handlers/word.py`, `src/handlers/excel.py`
- Risk: Graceful error handling relies on zipfile library. Unclear if all edge cases are covered.
- Recommendation: Priority: Low. Add a few fuzzing tests with deliberately corrupted fixtures.

**Untested: Formula Injection (Excel):**
- What's not tested: Comprehensive formula injection coverage. Current test (`test_formula_injection_prevented` in test_excel.py) checks the happy path. Edge cases like formulas with mixed case (`=cmd()` vs `=CMD()`) or Unicode variants not covered.
- Files: `src/handlers/excel_writer.py:49-57`
- Risk: A variant form of formula injection could slip through.
- Recommendation: Priority: Medium. Expand formula injection test to cover case variations and Unicode.

---

## Summary Table

| Concern Type | Count | Severity | Status |
|---|---|---|---|
| Tech Debt | 4 | Medium | Active |
| Known Bugs | 0 | - | None |
| Security | 5 | Low-Medium | Mitigated |
| Performance | 4 | Medium | Acceptable |
| Fragile Areas | 5 | Medium | Testable |
| Scaling Limits | 3 | Medium | Documented |
| Dependencies at Risk | 4 | Low-Medium | Monitored |
| Missing Features | 3 | Low | Out of Scope |
| Test Gaps | 6 | Medium | Known |

**Overall Assessment:** The codebase is production-ready for its intended use case (local form-filling MCP server). All critical security findings from the 2026-02-12 audit have been fixed. The identified concerns are either mitigated by design, acceptable for the current scope, or documented for future phases.
