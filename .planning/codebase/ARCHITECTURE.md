# Architecture

**Analysis Date:** 2026-02-16

## Pattern Overview

**Overall:** Deterministic document manipulation server using the Model Context Protocol (MCP). Stateless pipeline with clean separation between extraction (read-only), validation, and writing operations. No AI/LLM reasoning inside the server—all decision-making stays with the calling agent.

**Key Characteristics:**
- Format-agnostic pipeline (Word, Excel, PDF all follow same extract → validate → write → verify flow)
- Compact extraction with stable element IDs to keep responses agent-context-friendly
- No LLM calls within the server
- Pydantic models for all inputs/outputs
- Handler modules per format with shared utilities for XML, validation, and verification

## Layers

**MCP Tool Layer (Entry Points):**
- Location: `src/server.py`, `src/tools_extract.py`, `src/tools_write.py`
- Purpose: Register MCP tools with FastMCP, handle file input resolution, dispatch to format-specific handlers
- Contains: Tool decorators, request/response marshalling
- Depends on: handlers (word, excel, pdf), validators, models
- Used by: External MCP clients (copilot agents)

**Handler Layer (Format-Specific):**
- Word: `src/handlers/word.py` + sub-modules (parser, indexer, writer, verifier, validator, fields)
- Excel: `src/handlers/excel.py` + sub-modules (indexer, writer, verifier)
- PDF: `src/handlers/pdf.py` + sub-modules (indexer, writer, verifier)
- Purpose: Format-specific extraction, validation, writing, verification logic
- Depends on: xml_utils, validators, models, and format-specific libraries (lxml/python-docx for Word, openpyxl for Excel, PyMuPDF for PDF)
- Used by: MCP tool layer, other handler modules

**XML Utilities Layer (Word-Specific):**
- Location: `src/xml_utils.py`, `src/xml_snippet_matching.py`, `src/xml_formatting.py`, `src/xml_validation.py`
- Purpose: Reusable OOXML parsing, snippet matching, formatting extraction, XPath building, well-formedness validation
- Contains: Namespace handling, secure parser, snippet matching with whitespace normalization, run XML building
- Depends on: lxml
- Used by: Word handler modules, Word MCP tools

**Shared Utilities Layer:**
- Location: `src/models.py`, `src/validators.py`, `src/verification.py`, `src/mcp_app.py`
- Purpose: Pydantic data models, input validation (file type, path safety, size limits), confidence counting, summary building, FastMCP instance
- Contains: FileType/AnswerType/InsertionMode enums, request/response models, file resolver
- Depends on: pydantic, MCP
- Used by: All layers

## Data Flow

**Extract Pipeline (Read-Only):**

1. Agent calls `extract_structure_compact(file_path or file_bytes_b64)`
2. `tools_extract.py` → `resolve_file_input()` validates and loads file
3. Dispatches to format handler: `word_indexer.extract_structure_compact()`, `excel_indexer.extract_structure_compact()`, or `pdf_indexer.extract_structure_compact()`
4. Handler walks document structure:
   - Word: `word_indexer._parse_body()` → lxml parsing, assigns element IDs (P5, T1-R2-C1), builds `id_to_xpath` map
   - Excel: `excel_indexer._walk_sheets()` → openpyxl iteration, assigns cell IDs (S1-R2-C3)
   - PDF: `pdf_indexer._walk_widgets()` → PyMuPDF widget iteration, assigns field IDs (F1, F2, ...)
5. Returns `CompactStructureResponse`: compact_text (human-readable indexed), id_to_xpath (element ID → XPath), complex_elements (IDs needing raw XML)
6. Agent receives compact output (~few KB, safe for context window)

**Validation Pipeline:**

1. Agent calls `validate_locations(file_path, locations[])`
2. For each location (element ID, snippet, cell ID, or field ID):
   - Word with ID: Fast path — lookup in `id_to_xpath` map from prior extraction
   - Word with snippet: Slower path — `word_location_validator.find_snippet_in_body()` searches document XML
   - Excel with cell ID: Parse S-R-C format, confirm sheet/cell exists
   - PDF with field ID: Re-derive F-ID → native name mapping, confirm field exists
3. Returns `ValidatedLocation[]` with matched/not_found/ambiguous status and XPath

**Write Pipeline:**

1. Agent calls `write_answers(file_path, answers[])`
2. Agent has previously built answers using `build_insertion_xml()` for Word (plain_text or structured) or provides direct values (Excel/PDF)
3. For each answer: `{pair_id, xpath, insertion_xml, mode}`
   - Word: `word_writer.write_answers()` → locate element by XPath, apply mode (replace_content/append/replace_placeholder), repackage .docx ZIP
   - Excel: `excel_writer.write_answers()` → parse cell ID, set value via openpyxl, return .xlsx bytes
   - PDF: `pdf_writer.write_answers()` → lookup field name, set widget value via PyMuPDF, return PDF bytes
4. Returns filled document bytes (or writes to output_file_path if provided)

**Verification Pipeline:**

1. Agent calls `verify_output(filled_file_path, expected_answers[])`
2. Structural validation (Word only): checks no bare `<w:r>` under `<w:tc>`, every `<w:tc>` has `<w:p>`
3. Content verification: for each expected_answer, locate element, extract text, compare (case-insensitive substring match)
4. Confidence counting: tallies known/uncertain/unknown from `expected_answers[].confidence`
5. Returns `VerificationReport`: structural_issues[], content_results[], summary (total/matched/mismatched/missing + confidence breakdown)

**State Management:**

- Stateless — each MCP call is independent
- File input resolved at entry point (`resolve_file_input()` in `validators.py`)
- Two input modes: file_path (infers file_type from extension) or file_bytes_b64 (requires explicit file_type)
- `id_to_xpath` mapping returned with extraction so agent can validate locations without re-extracting

## Key Abstractions

**Element ID System:**
- Word: `T1-R2-C1` (table ID, row, cell), `P5` (paragraph)
- Excel: `S1-R2-C3` (sheet, row, column—all 1-indexed)
- PDF: `F1`, `F2`, ... (sequential field IDs in page order)
- Purpose: Stable references agent can use without seeing raw XML/JSON
- Implementation: Built during extraction, mapped in `id_to_xpath`, validated during `validate_locations()`

**Compact Representation:**
- Agent-friendly textual summary of document structure
- Example (Word): `T1-R1-C1: "Company Name" [bold]` followed by `T1-R1-C2: "" [empty, shaded] ← answer target`
- Purpose: Fits in context window (~few KB vs ~134KB raw OOXML) while preserving enough detail for agent reasoning
- Built by format handlers' `*_indexer.py` modules; uses `*_element_analysis.py` for text/formatting/complexity detection

**Insertion XML:**
- Pre-built, well-formed OOXML snippet (Word) or plain text value (Excel/PDF) ready to insert at a target location
- For Word plain_text answers: formatting inherited from target location via `xml_formatting.extract_formatting()` and `xml_formatting.build_run_xml()`
- For Word structured answers: agent provides OOXML; server validates with `xml_validation.is_well_formed_ooxml()`
- Purpose: Agent never has to hand-write OOXML; for structured cases, server validates before write
- Built by `build_insertion_xml()` MCP tool

**Snippet Matching (Word):**
- Core abstraction: `xml_snippet_matching.find_snippet_in_body()`
- Finds OOXML snippet in document body despite minor whitespace differences
- Returns XPath to matched element or None
- Used for `validate_locations()` with raw OOXML snippets and for `replace_placeholder` insertion mode
- Normalizes whitespace and namespace prefixes; flags ambiguous matches (snippet appears multiple times)

**XPath Navigation:**
- Enables precise element location in OOXML via `word_location_validator.validate_locations()`
- Validated paths: `/w:body/w:tbl[2]/w:tr[3]/w:tc[2]/w:p[1]`
- Generated by `xml_snippet_matching.build_xpath()` and extracted by `word_indexer` during compact extraction
- Used in write phase to locate insertion targets

## Entry Points

**MCP Server (Synchronous HTTP):**
- Location: `src/server.py`
- Triggers: `python -m src.server` or MCP client configuration
- Responsibilities: Import tool modules to trigger `@mcp.tool()` registration, call `mcp.run()` to start FastMCP server

**Extract Tools:**
- Location: `src/tools_extract.py`
- Triggers: MCP client calls `extract_structure_compact()`, `extract_structure()`, `validate_locations()`, `build_insertion_xml()`, or `list_form_fields()`
- Responsibilities: Validate file input, dispatch to format handler, return Pydantic model response

**Write Tools:**
- Location: `src/tools_write.py`
- Triggers: MCP client calls `write_answers()` or `verify_output()`
- Responsibilities: Validate answers array (or load from answers_file_path), dispatch to format handler, return filled document or verification report

## Error Handling

**Strategy:** Fail fast with specific error messages. No silent failures. Pydantic validation errors are caught and re-raised with context.

**Patterns:**

1. **File Input Validation** (`validators.py`):
   - Reject files > 50 MB (MAX_FILE_SIZE)
   - Reject base64 strings > 67 MB (MAX_BASE64_LENGTH)
   - Validate magic bytes (PK for .docx/.xlsx, %PDF for .pdf)
   - Validate file extension → file_type mapping
   - Raise `ValueError` with descriptive message if invalid

2. **Element Location Errors** (`word_location_validator.py`, etc.):
   - Return `ValidatedLocation` with `status: LocationStatus.NOT_FOUND` if element not found
   - Return `status: LocationStatus.AMBIGUOUS` if snippet matches multiple times
   - No exception; agent sees status and decides next action

3. **OOXML Parsing Errors** (`xml_utils.py`):
   - Secure parser with `recover=False` to fail on malformed XML
   - `is_well_formed_ooxml()` returns `(bool, str | None)` — valid flag and error message
   - Agent receives error in `BuildInsertionXmlResponse.error` field

4. **Write Errors** (`word_writer.py`, `excel_writer.py`, `pdf_writer.py`):
   - Path safety validation: reject XPaths/cell IDs/field names that don't match expected format
   - Raise `ValueError` if XPath unsafe (fails `_XPATH_SAFE_RE` regex) or cell ID unparseable
   - Let underlying libraries (lxml, openpyxl, PyMuPDF) raise on data corruption; let those propagate

5. **Verification Errors** (`word_verifier.py`, etc.):
   - Structural issues collected in list (not exceptions) and returned in `VerificationReport.structural_issues`
   - Content mismatches marked as `ContentStatus.MISMATCHED` or `MISSING`, not exceptions
   - Summary provides counts for agent to assess results

## Cross-Cutting Concerns

**Logging:**
- No logging framework in use. Errors surface as exceptions or return-value fields.
- Future: Could add `logging` module if needed; currently relies on agent to examine response fields.

**Validation:**
- Input validation: file type, path safety, size limits (in `validators.py`)
- Output validation: OOXML well-formedness (in `xml_validation.py`), document structural integrity (in `*_verifier.py` modules)
- Data model validation: Pydantic ensures all MCP responses match declared schema

**Authentication:**
- None. Server is stateless and documenmt-agnostic. All authorization decisions live with the calling agent.
- Privacy: No data persistence; documents not sent to external services.

**Format Detection:**
- Auto-detect from file extension: `.docx` → Word, `.xlsx` → Excel, `.pdf` → PDF
- Can be overridden by explicit `file_type` parameter (useful for non-standard extensions)
- Magic byte validation ensures file actually matches declared type

**Dependency Resolution:**
- Clean import hierarchy: `server.py` → `tools_*` → `handlers` → `xml_utils`/`validators` → `models`
- No circular imports
- Shared constants (namespaces, limits) centralized in `validators.py` and `xml_utils.py`
- `xml_utils.py` is a re-export barrel for `xml_snippet_matching`, `xml_formatting`, `xml_validation` to avoid multiple imports in handlers

---

*Architecture analysis: 2026-02-16*
