# Codebase Structure

**Analysis Date:** 2026-02-16

## Directory Layout

```
vibe-legal-form-filler/
├── src/                          # Python package — MCP server code
│   ├── __init__.py
│   ├── server.py                 # Entry point: imports tool modules, runs MCP server
│   ├── mcp_app.py                # FastMCP instance shared across tool modules
│   ├── tools_extract.py          # MCP tools: extract, validate, build_xml, list_fields
│   ├── tools_write.py            # MCP tools: write_answers, verify_output
│   ├── models.py                 # Pydantic models: FileType, AnswerType, etc.
│   ├── handlers/                 # Format-specific implementation (word, excel, pdf)
│   │   ├── __init__.py
│   │   ├── word.py               # Word public API — delegates to sub-modules
│   │   ├── word_parser.py        # .docx ZIP extraction and XML parsing
│   │   ├── word_indexer.py       # Compact extraction: walks body, assigns element IDs
│   │   ├── word_element_analysis.py  # Helpers: extract text, formatting, complexity detection
│   │   ├── word_location_validator.py  # Location validation: XPath lookup, snippet matching
│   │   ├── word_writer.py        # Answer insertion: XPath-based content replacement
│   │   ├── word_fields.py        # Form field detection: empty cells, placeholders
│   │   ├── word_verifier.py      # Structural + content verification
│   │   ├── excel.py              # Excel public API — delegates to sub-modules
│   │   ├── excel_indexer.py      # Compact extraction: walks sheets/rows/cells, assigns S-R-C IDs
│   │   ├── excel_writer.py       # Answer insertion: writes cell values via openpyxl
│   │   ├── excel_verifier.py     # Content verification: reads cells and compares
│   │   ├── pdf.py                # PDF public API — delegates to sub-modules
│   │   ├── pdf_indexer.py        # Compact extraction: walks AcroForm widgets, assigns F-IDs
│   │   ├── pdf_writer.py         # Answer insertion: sets widget values via PyMuPDF
│   │   └── pdf_verifier.py       # Content verification: reads widget values and compares
│   ├── xml_utils.py              # OOXML re-export barrel (snippet matching, formatting, validation)
│   ├── xml_snippet_matching.py   # Core: snippet matching, XPath building, structural comparison
│   ├── xml_formatting.py         # OOXML formatting extraction, run XML building
│   ├── xml_validation.py         # OOXML well-formedness and element whitelist validation
│   ├── validators.py             # Shared validation: file type, path safety, size limits
│   └── verification.py           # Shared verification: confidence counting, summary building
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_word.py              # Word handler tests
│   ├── test_word_indexer.py      # Word compact extraction tests
│   ├── test_word_verifier.py     # Word verification tests
│   ├── test_excel.py             # Excel handler tests
│   ├── test_pdf.py               # PDF handler tests
│   ├── test_xml_utils.py         # XML utilities tests
│   ├── test_file_path.py         # File input validation tests
│   ├── test_e2e_integration.py   # End-to-end pipeline tests
│   ├── e2e_word_test.py          # Word pipeline integration tests
│   ├── create_fixtures.py        # Test fixture generation
│   ├── fixtures/                 # Sample form documents for testing
│   │   ├── placeholder_form.docx
│   │   ├── table_questionnaire.docx
│   │   ├── vendor_assessment.xlsx
│   │   ├── simple_form.pdf
│   │   ├── multi_page_form.pdf
│   │   ├── prefilled_form.pdf
│   │   └── create_pdf_fixtures.py
│   ├── inputs/                   # Test input documents
│   ├── outputs/                  # Test output documents
│   └── __pycache__/
├── docs/                         # Documentation
├── .planning/                    # GSD planning documents
│   └── codebase/
├── README.md                     # User-facing documentation
├── CLAUDE.md                     # Maintenance guide for AI assistants
├── pyproject.toml               # Python project metadata and dependencies
├── requirements.txt             # Pip dependencies
├── LICENSE                      # AGPL-3.0 license
├── NOTICE                       # Dual licensing note
└── SELF_TEST_REPORT.md         # Test results and coverage
```

## Directory Purposes

**`src/`:**
- Purpose: Main Python package containing MCP server and all handler logic
- Contains: Server entry point, MCP tool functions, format handlers, XML utilities, validation logic
- Key files: `server.py` (entry point), `mcp_app.py` (FastMCP instance), `models.py` (data contracts)

**`src/handlers/`:**
- Purpose: Format-specific document handling (Word, Excel, PDF)
- Contains: One set of modules per format (word*.py, excel*.py, pdf*.py)
- Pattern: Each format has a public API file (word.py, excel.py, pdf.py) that delegates to focused sub-modules

**`tests/`:**
- Purpose: Test suite covering handlers, XML utilities, file validation, and end-to-end pipelines
- Contains: Unit tests, integration tests, fixture generation scripts
- Fixtures: Sample .docx, .xlsx, .pdf files representing different document types (questionnaires, forms, vendor assessments)

**`docs/`:**
- Purpose: Architecture and design documentation
- Currently minimal; CLAUDE.md serves as detailed maintenance guide

## Key File Locations

**Entry Points:**
- `src/server.py`: MCP server startup — imports tool modules to trigger `@mcp.tool()` registration, then runs `mcp.run()`

**MCP Tool Definitions:**
- `src/tools_extract.py`: Read-only tools (extract_structure_compact, extract_structure, validate_locations, build_insertion_xml, list_form_fields)
- `src/tools_write.py`: Write tools (write_answers, verify_output)

**Configuration:**
- `pyproject.toml`: Project metadata, Python version requirement (3.11+), dependencies
- `requirements.txt`: Pip freeze format, used by some deployment environments

**Core Logic (Word):**
- `src/handlers/word_indexer.py`: Compact extraction — walks `<w:body>`, assigns element IDs, builds `id_to_xpath`
- `src/handlers/word_location_validator.py`: Location validation — XPath lookup and snippet matching
- `src/handlers/word_writer.py`: Answer insertion — locate target by XPath, apply insertion mode, repackage .docx ZIP
- `src/handlers/word_verifier.py`: Post-write verification — structural checks and content comparison

**Core Logic (Excel):**
- `src/handlers/excel_indexer.py`: Compact extraction — walks sheets/rows/cells, assigns S1-R2-C3 IDs
- `src/handlers/excel_writer.py`: Answer insertion — parse cell ID, set value via openpyxl
- `src/handlers/excel_verifier.py`: Post-write verification — read cells, compare to expected

**Core Logic (PDF):**
- `src/handlers/pdf_indexer.py`: Compact extraction — walks AcroForm widgets, assigns F-IDs, extracts nearby text
- `src/handlers/pdf_writer.py`: Answer insertion — lookup field name, set widget value via PyMuPDF
- `src/handlers/pdf_verifier.py`: Post-write verification — read widget values, compare to expected

**XML Utilities (Word-Specific):**
- `src/xml_snippet_matching.py`: Find OOXML snippet in document, build XPath, normalize whitespace
- `src/xml_formatting.py`: Extract formatting from element context, build run XML with inheritance
- `src/xml_validation.py`: Check well-formedness, validate element whitelist

**Shared Utilities:**
- `src/models.py`: Pydantic data models for all MCP requests/responses
- `src/validators.py`: File type validation, path safety, size limits, file input resolver
- `src/verification.py`: Confidence counting, verification summary building

**Testing:**
- `tests/test_word.py`: Unit tests for word.py public API
- `tests/test_word_indexer.py`: Unit tests for compact extraction
- `tests/test_word_verifier.py`: Unit tests for verification
- `tests/test_excel.py`, `tests/test_pdf.py`: Equivalent tests for Excel and PDF handlers
- `tests/test_e2e_integration.py`: End-to-end pipeline tests (extract → validate → write → verify)
- `tests/fixtures/`: Sample .docx, .xlsx, .pdf files

## Naming Conventions

**Files:**
- Modules follow snake_case: `word_indexer.py`, `pdf_writer.py`
- Test modules: `test_<module>.py` (e.g., `test_word_indexer.py`)
- No abbreviations in public module names (use `word_location_validator` not `word_loc_val`)

**Directories:**
- snake_case: `src/handlers/`
- Plural form for collections: `tests/`, `fixtures/`, `docs/`

**Functions (public):**
- snake_case: `extract_structure_compact()`, `validate_locations()`, `write_answers()`
- Descriptive, no abbreviations in public API
- Private (module-internal) functions: prefix with `_`: `_parse_body()`, `_index_table()`

**Functions (handlers):**
- Consistent signatures across formats:
  - Extraction: `extract_structure_compact(file_bytes: bytes) → CompactStructureResponse`
  - Validation: `validate_locations(file_bytes: bytes, locations: list[LocationSnippet]) → list[ValidatedLocation]`
  - Writing: `write_answers(file_bytes: bytes, answers: list[AnswerPayload]) → bytes`
  - Verification: `verify_output(file_bytes: bytes, expected_answers: list[ExpectedAnswer]) → VerificationReport`

**Classes (Pydantic models):**
- PascalCase: `CompactStructureResponse`, `AnswerPayload`, `ValidatedLocation`
- Enums: `FileType`, `InsertionMode`, `ContentStatus`

**Variables:**
- snake_case: `id_to_xpath`, `body_xml`, `complex_elements`
- Constants (module-level): UPPER_SNAKE_CASE: `NAMESPACES`, `MAX_FILE_SIZE`, `WORD_NAMESPACE_URI`

## Where to Add New Code

**New Format (e.g., add PowerPoint support):**
1. Create `src/handlers/ppt.py` — public API
2. Create `src/handlers/ppt_parser.py` — file loading and structure parsing
3. Create `src/handlers/ppt_indexer.py` — compact extraction with element ID assignment
4. Create `src/handlers/ppt_location_validator.py` — location validation
5. Create `src/handlers/ppt_writer.py` — answer insertion
6. Create `src/handlers/ppt_verifier.py` — post-write verification
7. Add `FileType.PPT` to `models.py`
8. Update `tools_extract.py` to dispatch PowerPoint requests
9. Update `tools_write.py` to dispatch PowerPoint requests
10. Add tests: `tests/test_ppt.py` and format-specific test files

**New Tool (e.g., extract_plain_text):**
1. Add to `tools_extract.py` with `@mcp.tool()` decorator
2. Use `resolve_file_input()` to handle file_path/file_bytes_b64 modes
3. Dispatch to format handlers (create methods in `word.py`, `excel.py`, `pdf.py` if needed)
4. Add request/response Pydantic models to `models.py`
5. Add test file `tests/test_<tool_name>.py`

**New Utility (e.g., element ID validator):**
1. Create new module in `src/` if cross-format, or in `src/handlers/` if format-specific
2. Name clearly: `element_id_utils.py` or `word_element_id_utils.py`
3. Keep functions focused (max 40 lines); extract helpers for reusable logic
4. Add docstrings explaining what, why, and when to call
5. Import in relevant handler module
6. Add tests in new test file

**New Handler Sub-Module:**
- Keep under 200 lines; follow naming pattern `<format>_<operation>.py`
- Re-export public API in `<format>.py` if it's called from outside handlers
- Import from utilities via barrel exports (`from src.xml_utils import ...`)

## Special Directories

**`tests/fixtures/`:**
- Purpose: Sample form documents for testing
- Files: `.docx`, `.xlsx`, `.pdf` files representing different form types
- Generated: By `tests/fixtures/create_pdf_fixtures.py` and `tests/create_fixtures.py`
- Committed: Yes — fixtures are part of test suite

**`tests/inputs/` and `tests/outputs/`:**
- Purpose: Temporary input and output files during test runs
- Generated: Yes — tests create files here
- Committed: No — `.gitignore` excludes test I/O

**`.planning/codebase/`:**
- Purpose: GSD-generated codebase analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: By Claude Agent when `/gsd:map-codebase` is invoked
- Committed: Yes — documents are version-controlled for easy reference

## File Size Guidelines

- No file should exceed 200 lines
- Current status: All files within limit
- If a handler approaches 200 lines, split into focused modules
- Example: `word.py` is thin (100 lines); complex logic in sub-modules (`word_indexer.py`, `word_writer.py`, etc.)

## Module Structure Pattern

Each format handler follows this structure:

1. **Public API file** (`word.py`, `excel.py`, `pdf.py`):
   - Imports from sub-modules
   - Re-exports public functions with `# noqa: F401` for clarity
   - Each public function is thin (10-20 lines) and delegates to sub-modules
   - Docstrings explain the tool's purpose from MCP perspective

2. **Indexer sub-module** (`*_indexer.py`):
   - `extract_structure_compact(file_bytes) → CompactStructureResponse`
   - Walks document structure, assigns stable element IDs
   - Returns compact_text (human-readable), id_to_xpath (mapping), complex_elements (flags)

3. **Validator sub-module** (`*_location_validator.py`, Word only):
   - `validate_locations(file_bytes, locations[]) → ValidatedLocation[]`
   - Confirms element IDs/snippets exist in document

4. **Writer sub-module** (`*_writer.py`):
   - `write_answers(file_bytes, answers[]) → bytes`
   - Inserts content at specified locations, returns modified document

5. **Verifier sub-module** (`*_verifier.py`):
   - `verify_output(file_bytes, expected_answers[]) → VerificationReport`
   - Checks structural validity and compares expected vs actual content

6. **Helper sub-modules** (format-specific):
   - Word: `word_parser.py` (ZIP/XML loading), `word_element_analysis.py` (text/formatting detection), `word_fields.py` (form field detection)
   - Excel: (handlers are thin; logic lives in indexer/writer/verifier)
   - PDF: (handlers are thin; logic lives in indexer/writer/verifier)

---

*Structure analysis: 2026-02-16*
