# Form Filler MCP Server

## What This Is

An MCP server that exposes form-filling tools for copilot agents. It handles the deterministic side of form filling — reading document structure, validating locations, building insertion XML, and writing answers back. The calling agent handles all AI reasoning (identifying pairs, generating answers). This server never makes LLM calls.

The typical use case: a company sets up a copilot agent with its institutional knowledge already loaded (company policies, previous questionnaires, standard answers, corporate data). When a user receives a questionnaire, they drop it into the agent. The agent calls this MCP server to extract the form structure, identifies the questions, draws on its own knowledge plus any user instructions ("our D&O coverage is $10M", "use the London office address") to generate answers, then calls the server again to write those answers back into the document.

The MCP server's job is strictly document manipulation. All knowledge — institutional and ad-hoc — lives with the agent.

Supports Word (.docx), Excel (.xlsx), and PDF (fillable AcroForm). Word and Excel handlers are complete and MCP-verified. PDF is the final format.

## Core Design Principle

AI is bad at writing large amounts of correct OOXML from scratch. The server does the heavy XML parsing and gives the agent a compact, human-readable representation with stable element IDs. The agent works with IDs and plain text — never raw OOXML. So we split the work:

- **Code parses** the OOXML and returns a compact indexed representation with element IDs
- **AI reads** the compact representation and identifies question/answer pairs by ID
- **Code validates** that each element ID maps to a real location in the document
- **AI answers** the questions using the agent's institutional knowledge and user instructions (plain text only, no OOXML)
- **Code builds** the insertion OOXML (for plain text answers) or **AI builds** a small OOXML snippet (for structured answers like checkboxes)
- **Code validates** any AI-generated insertion XML is well-formed
- **Code writes** the answer into the document at the located position

The MCP server owns steps: parse structure, validate locations, build plain insertion XML, validate insertion XML, and write. The calling agent owns: identify pairs by ID, generate answers (using its own knowledge + user instructions), and optionally build structured insertion XML.

### Why Compact Extraction

MCP tool responses go directly into the calling agent's conversation context. A typical Word questionnaire produces ~134KB of raw OOXML — far too large for a conversation turn. The `extract_structure_compact` tool solves this by doing the heavy XML parsing server-side and returning a compact representation (a few KB) with stable element IDs. The agent never needs to see or produce raw OOXML. The raw `extract_structure` tool remains available for specialized agents with large context windows.

## File Input

Every tool that takes a document accepts two input modes:

- **`file_path`** *(preferred for interactive agents)* — an absolute or relative path to the file on disk. The server reads the bytes and infers `file_type` from the extension (`.docx`→word, `.xlsx`→excel, `.pdf`→pdf).
- **`file_bytes_b64`** *(for programmatic use)* — base64-encoded file bytes. Requires `file_type` to be provided explicitly.

Provide one or the other. If both are provided, `file_path` takes precedence. If `file_path` is used, `file_type` is optional (inferred from extension) but can be provided to override.

The `write_answers` tool also accepts an optional **`output_file_path`** — when provided, the server writes the filled document to that path on disk instead of returning base64-encoded bytes.

## The Pipeline

```
STEP 1: EXTRACT STRUCTURE (MCP tool — deterministic)
  Default:  extract_structure_compact (recommended for most agents)
    Input:  form document bytes, file type
    Output: JSON with compact_text (indexed human-readable representation),
            id_to_xpath (ID → XPath mapping), complex_elements (IDs needing raw XML)
    Note:   response is a few KB, not 134KB — safe for conversation context

  Alternative: extract_structure (for agents with large context windows)
    Input:  form document bytes, file type
    Output: full OOXML body as text (for Word), or structured representation
    Note:   returns raw XML; agent must work with OOXML snippets instead of IDs

STEP 2: VALIDATE LOCATIONS (MCP tool — deterministic)
  Input:  document bytes, array of element IDs (from compact) or OOXML snippets (from raw)
  Output: validated array with match status and XPath for each location
  Action: for IDs — looks up XPath from the id_to_xpath mapping
          for snippets — searches document XML for the snippet
          returns the XPath or element reference for each match

STEP 3: BUILD INSERTION XML (MCP tool — deterministic)
  Input:  answer text, target location context, answer_type
  Output: well-formed OOXML run/paragraph ready for insertion
  Note:   for answer_type "plain_text" — code templates the XML,
          inheriting formatting from the target location
          for answer_type "structured" — the calling agent provides
          AI-generated OOXML which this tool validates only

STEP 4: WRITE ANSWERS (MCP tool — deterministic)
  Input:  document bytes, array of {xpath, insertion_xml} pairs
  Output: completed document bytes with all answers inserted
  Action: locates each target in the XML tree, inserts the answer,
          preserves all other document structure and formatting

STEP 5: VERIFY OUTPUT (MCP tool — deterministic)
  Input:  filled document bytes, array of {pair_id, xpath, expected_text}
  Output: verification report with structural issues and content results
  Action: checks OOXML structural integrity (no bare w:r under w:tc,
          every w:tc has a w:p), then compares expected text vs actual
          text at each XPath location
```

### Where Knowledge Lives

The MCP server has no knowledge layer. All knowledge sits with the copilot agent:

- **Institutional knowledge** — loaded when the agent is configured (company policies, standard answers, corporate data, previous questionnaires). This is the agent's built-in context.
- **User instructions** — provided at runtime ("our CEO is Jane Smith", "coverage limit is $10M"). The agent receives these directly.
- **Additional documents** — if the user attaches reference files alongside the form, the agent can read them using its own file handling. The MCP server provides an optional `extract_text` utility to help parse non-trivial formats, but this is a convenience, not a core pipeline step.

The agent combines all three sources when generating answers. The MCP server only sees the form document itself.

### How the Calling Agent Orchestrates This

```
1. User drops in: form document path + optional reference/knowledge documents + instructions
2. Agent calls extract_structure_compact(file_path="form.docx")
   → gets compact indexed representation (no base64 encoding needed)
   NOTE: MCP tools are only for the form being filled, not reference documents.
3. Agent reads reference/knowledge documents using its own native file tools
   (not MCP tools). These provide the answers the agent will use.
4. Agent reads compact_text → identifies question/answer pairs by element ID
   (AI uses agent's institutional knowledge + reference docs to understand context)
5. Agent calls validate_locations(file_path="form.docx", ...) → confirms IDs are real
6. Agent generates answers using: institutional knowledge + reference docs + user instructions
   For each question, assess confidence: "known", "uncertain", or "unknown".
   Do NOT include "unknown" answers in the write_answers call — leave those cells empty.
7. Agent calls build_insertion_xml for each answer → gets OOXML to insert
8. Agent calls write_answers(file_path="form.docx", output_file_path="filled.docx", ...)
   → filled document written to disk
   For large answer sets (>20), write answers to a JSON file and use answers_file_path.
9. Agent calls verify_output(file_path="filled.docx", expected_answers=[...])
   → confirms all answers were written correctly and structure is valid
   Include confidence field on each expected_answer for the summary report.
10. Agent reports unknown questions to the user for manual completion.
```

## MCP Tools

### `extract_structure_compact(file_path | file_bytes_b64, file_type?) → compact representation` *(primary)*

The default first step in the pipeline. Walks the document body and returns a compact, human-readable indexed representation instead of raw XML. Designed to fit comfortably in an agent's conversation context (a few KB, not 134KB). Use this on the form/questionnaire you want to fill — not on reference or knowledge documents.

For Word, the response contains:
- **`compact_text`** — indexed representation with stable element IDs and text content
- **`id_to_xpath`** — mapping from every element ID to its XPath in the document
- **`complex_elements`** — list of IDs flagged as containing complex OOXML

For Excel, the response contains:
- **`compact_text`** — indexed representation with sheet headers and cell IDs
- **`id_to_xpath`** — identity mapping (cell ID → cell ID, since the ID is the reference)
- **`complex_elements`** — always empty (Excel has no complex OOXML)

For PDF, the response contains:
- **`compact_text`** — human-readable inventory of all fillable AcroForm fields, grouped by page, with field types, current values, and nearby text context
- **`id_to_field`** — mapping from sequential field ID (F1, F2, ...) to native field name, page number, field type, and options (for dropdowns/radio)
- **`complex_elements`** — always empty (AcroForm fields are simple)
- **`summary`** — total fields, pages with fields, empty vs pre-filled counts

**Element ID scheme (Word):**
- `T1-R2-C1` — table 1, row 2, cell 1
- `P5` — paragraph 5 (top-level, outside any table)

**Element ID scheme (Excel):**
- `S1-R2-C3` — sheet 1, row 2, column 3 (all 1-indexed, matching openpyxl)

**Element ID scheme (PDF):**
- `F1`, `F2`, `F3` — sequential field IDs assigned in page order. Stable within a single extraction. Mapped to native field names via `id_to_field`.

**For simple elements:** outputs ID, text content, and formatting hints (bold, italic, shading, font size).

**For complex elements** (nested tables, content controls `w:sdt`, legacy form fields `w:fldChar`, merged cells `gridSpan`/`vMerge`, text boxes, embedded objects): outputs ID, a `COMPLEX` warning with the type, and the raw XML snippet for just that element.

**Empty cells and placeholders** (e.g. "[Enter here]", "___") are marked as potential answer targets.

Example compact_text output:
```
T1-R1-C1: "Company Name" [bold]
T1-R1-C2: "" [empty, shaded] ← answer target
T1-R2-C1: "Date of Incorporation"
T1-R2-C2: "" [empty, shaded] ← answer target
P3: "Please describe your data security policies:" [bold]
P4: "[Enter here]" [placeholder] ← answer target
T2-R1-C1: "Coverage Type" [bold]
T2-R1-C2: "Limit" [bold]
T2-R1-C3: "Deductible" [bold]
T2-R2-C1: "General Liability"
T2-R2-C2: "" [empty] ← answer target
T2-R2-C3: COMPLEX(gridSpan=2): <w:tc>...</w:tc>
```

Example compact_text output (Excel):
```
=== Sheet 1: "Company Information" ===
S1-R1-C1: "Question" [bold]
S1-R1-C2: "Response" [bold]
S1-R2-C1: "Legal Entity Name"
S1-R2-C2: "" [empty] ← answer target
S1-R3-C1: "Registration Number"
S1-R3-C2: "" [empty] ← answer target
S1-R8-C1: "Primary Contact"
S1-R8-C2: "Jane Smith"
=== Sheet 2: "Insurance Coverage" ===
S2-R1-C1: "Coverage Type" [bold]
S2-R1-C2: "Policy Limit" [bold]
S2-R2-C1: "Professional Indemnity"
S2-R2-C2: "" [empty] ← answer target
S2-R5-C1: "Notes:" [merged: S2-R5-C1:S2-R6-C1]
```

Example compact_text output (PDF):
```
=== PDF Form: 12 fields across 3 pages ===

Page 1:
[F1] "employee_name" (text) — empty
    Context: Employee Information | Full Legal Name | First Middle Last
[F2] "start_date" (text) — empty
    Context: Employment Details | Start Date | MM/DD/YYYY
[F3] "fulltime_cb" (checkbox) — unchecked
    Context: Employment Type | Full Time | Part Time
[F4] "dept_dd" (dropdown, options: HR | Engineering | Sales | Finance) — empty
    Context: Department Assignment | Select Department

Page 2:
[F5] "signature" (text) — empty
    Context: Authorization | Employee Signature | Date
```

### `extract_structure(file_path | file_bytes_b64, file_type?) → document structure` *(alternative)*

Returns the raw OOXML body (Word) or structured representation (Excel/PDF). Use this only when the calling agent has a large context window and needs to work directly with raw XML. Use on the form being filled — not on reference or knowledge documents.

For Word: returns the full `<w:body>` XML as a string (~134KB for a typical questionnaire). The calling agent sends this to AI with a prompt like "identify question/answer pairs and return each answer location as an OOXML snippet."

For Excel: returns a JSON representation of sheets, rows, columns, merged cells, and cell values.

For PDF: returns a JSON list of all AcroForm fields with native field names, types, current values, page numbers, and options (for dropdowns/radio). Same data as compact but in structured form without the human-readable text or nearby context.

### `extract_text(file_bytes, file_type) → text content` *(optional utility)*

A convenience tool for when the agent needs to read an attached document that isn't the form itself — for example, if the user drops in a reference PDF alongside the questionnaire. Extracts plain text from Word, Excel, PDF, or TXT files.

This is not part of the core pipeline. Most copilot agents can read files natively. This tool exists for agents that cannot, or for non-trivial formats where python-docx/openpyxl/PyMuPDF would do a better job than the agent's built-in file reader.

### `validate_locations(file_path | file_bytes_b64, file_type?, locations[]) → validated_locations[]`

Each location is an element ID like `T1-R2-C2` (from compact extraction), an OOXML snippet (from raw extraction), a cell reference (Excel), or a field name (PDF).

For Word with element IDs: looks up the XPath from the `id_to_xpath` mapping returned by `extract_structure_compact`. Returns match/no-match and the XPath. This is the fast path — no snippet searching needed.

For Word with OOXML snippets: searches the document XML for each snippet. Returns match/no-match and the XPath to the matched element. Handles minor whitespace differences. Flags ambiguous matches (snippet appears more than once).

For Excel: confirms cell IDs (S1-R2-C3) exist in the workbook. Parses the ID to extract sheet index, row, and column. Checks that the sheet exists and the cell is within the worksheet's used dimensions. Returns the cell ID as the xpath and the cell's current value as context.

For PDF: accepts field IDs (F1, F2, etc.) from compact extraction. Looks up the native field name from the `id_to_field` mapping. Confirms the field exists in the PDF. Returns the field's native name as context.

Returns (Word example):
```json
[
  {
    "pair_id": "q1",
    "status": "matched",
    "xpath": "/w:body/w:tbl[2]/w:tr[3]/w:tc[2]/w:p[1]",
    "context": "neighbouring text for human review"
  }
]
```

Returns (Excel example):
```json
[
  {
    "pair_id": "q1",
    "status": "matched",
    "xpath": "S1-R2-C2",
    "context": "current cell value or empty"
  }
]
```

Returns (PDF example):
```json
[
  {
    "pair_id": "q1",
    "status": "matched",
    "xpath": "F1",
    "context": "employee_name (text)"
  }
]
```

### `build_insertion_xml(answer_text, target_context_xml, answer_type) → insertion_xml`

For `answer_type: "plain_text"` (the common case):
- Reads the formatting (font, size, style) from the target location XML
- Wraps the answer text in a `<w:r>` element inheriting that formatting
- Returns well-formed OOXML ready to insert

For `answer_type: "structured"`:
- Expects the calling agent to provide AI-generated OOXML in `answer_text`
- Validates it is well-formed XML
- Validates it uses only legitimate OOXML elements and attributes
- Returns it if valid, returns an error if not

For Excel: not needed — openpyxl writes cell values directly.

For PDF: not needed — PyMuPDF writes field values directly via widget API.

### `write_answers(file_path | file_bytes_b64, file_type?, answers[]?, answers_file_path?, output_file_path?) → filled_file_bytes`

Each answer (Word):
```json
{
  "pair_id": "q1",
  "xpath": "/w:body/w:tbl[2]/w:tr[3]/w:tc[2]/w:p[1]",
  "insertion_xml": "<w:r><w:rPr><w:rFonts w:ascii='Calibri'/><w:sz w:val='22'/></w:rPr><w:t>Answer text here</w:t></w:r>",
  "mode": "replace_content"
}
```

Each answer (Excel — simpler, no insertion XML needed):
```json
{
  "pair_id": "q1",
  "xpath": "S1-R2-C2",
  "insertion_xml": "Acme Corporation",
  "mode": "replace_content"
}
```

For Excel, `insertion_xml` holds the plain text cell value (not XML). Only `replace_content` mode is supported — it writes the value directly to the cell using openpyxl.

Each answer (PDF — simplest, field ID + value):
```json
{
  "pair_id": "q1",
  "xpath": "F1",
  "insertion_xml": "John Smith",
  "mode": "replace_content"
}
```

For PDF, `xpath` holds the field ID (F1, F2, etc.), `insertion_xml` holds the plain text value. The server looks up the native field name from the `id_to_field` mapping, then sets the value via PyMuPDF's widget API. Type-specific logic:
- **Text fields**: `widget.field_value = str(value)`
- **Checkboxes**: coerce "true"/"yes"/"1"/"checked" to bool
- **Dropdowns**: validate value is in the options list, then set
- **Radio buttons**: set `widget.field_value = str(value)`

**`answers_file_path`** *(recommended for large payloads)* — path to a JSON file containing the answers array. The agent writes its answers to a JSON file on disk and passes the path instead of inlining 50+ answer objects as tool parameters. This avoids overwhelming the agent's context window during generation. JSON schema: `[{"pair_id": "q1", "xpath": "S1-R2-C3", "insertion_xml": "answer text", "mode": "replace_content"}, ...]`. The inline `answers` parameter remains as a fallback for small payloads.

Modes (Word):
- `replace_content` — clears existing content in the target element, inserts new
- `append` — adds after existing content
- `replace_placeholder` — finds placeholder text (e.g. "[Enter here]") within the target and replaces only that

Returns the complete document as bytes with all answers inserted. When `output_file_path` is provided, writes the result to disk and returns the path instead of base64 bytes.

### `verify_output(file_path | file_bytes_b64, file_type?, expected_answers[]) → verification_report`

Post-write verification tool. Runs after `write_answers` to confirm the output document is structurally valid and all answers were written correctly.

Each expected_answer is:
```json
{
  "pair_id": "q1",
  "xpath": "/w:body/w:tbl[2]/w:tr[3]/w:tc[2]",
  "expected_text": "Acme Corporation",
  "confidence": "known"
}
```

**Structural validation** (Word):
- No bare `<w:r>` directly under `<w:tc>` (runs must be inside paragraphs)
- Every `<w:tc>` has at least one `<w:p>` child

**Structural validation** (Excel):
- No structural validation needed (openpyxl guarantees valid .xlsx output)
- Returns empty structural_issues list

**Structural validation** (PDF):
- No structural validation needed (PyMuPDF handles PDF integrity)
- Returns empty structural_issues list

**Content verification:**
- For each expected_answer, locates the element at the XPath (Word), cell ID (Excel), or field ID (PDF)
- Extracts text content and compares against expected_text (case-insensitive substring match)

The optional **`confidence`** field (`"known"`, `"uncertain"`, `"unknown"`, default `"known"`) is carried through for reporting. The summary includes confidence counts so the user knows how many answers need manual review.

Returns:
```json
{
  "structural_issues": ["Bare <w:r> found directly under <w:tc>"],
  "content_results": [
    {"pair_id": "q1", "status": "matched", "expected": "Acme Corp", "actual": "Acme Corp"}
  ],
  "summary": {
    "total": 53, "matched": 50, "mismatched": 0, "missing": 3, "structural_issues": 0,
    "confidence_known": 42, "confidence_uncertain": 3, "confidence_unknown": 8,
    "confidence_note": "42 known, 3 uncertain, 8 unknown — manual review needed"
  }
}
```

### `list_form_fields(file_path | file_bytes_b64, file_type?) → fields[]`

A simpler utility. Returns a plain inventory of all fillable targets found by code (not AI). For Word: empty table cells following a cell with text, paragraphs containing common placeholders. For Excel: empty cells adjacent to cells with question-like text. For PDF: all native AcroForm fields with their types and current values (no nearby text extraction).

## Project Structure

```
vibe-legal-form-filler/
├── CLAUDE.md
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── server.py              # MCP server entry point — thin, imports tool modules, runs mcp
│   ├── mcp_app.py             # FastMCP instance (shared across tool modules)
│   ├── tools_extract.py       # MCP tools: extract_compact, extract, validate, build_xml, list_fields
│   ├── tools_write.py         # MCP tools: write_answers, verify_output
│   ├── models.py              # Pydantic models for pairs, locations, answers
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── word.py            # Word handler: public API (extract, build XML, write, list fields)
│   │   ├── word_parser.py     # .docx XML extraction (shared by word handler modules)
│   │   ├── word_indexer.py    # Compact extraction: walks OOXML body, assigns element IDs
│   │   ├── word_location_validator.py  # Location validation: element IDs and snippet matching
│   │   ├── word_element_analysis.py    # Element text/formatting/complexity detection helpers
│   │   ├── word_writer.py     # Answer insertion: XPath-based content replacement
│   │   ├── word_fields.py     # Form field detection: empty cells, placeholders
│   │   ├── word_verifier.py   # Post-write verification: structural + content checks
│   │   ├── excel.py           # Excel handler: extract, validate, write (thin entry point)
│   │   ├── excel_indexer.py   # Compact extraction: walks sheets/rows/cells, assigns S-R-C IDs
│   │   ├── excel_writer.py    # Answer insertion: writes cell values using openpyxl
│   │   ├── excel_verifier.py  # Post-write verification: reads cells and compares to expected
│   │   ├── pdf.py             # PDF handler: thin entry point, delegates to sub-modules
│   │   ├── pdf_indexer.py     # Compact extraction: walks AcroForm widgets, assigns F-IDs
│   │   ├── pdf_writer.py      # Answer insertion: sets widget values via PyMuPDF
│   │   ├── pdf_verifier.py    # Post-write verification: reads widget values and compares
│   │   └── text_extractor.py  # Optional: extract plain text from any supported format
│   ├── xml_utils.py           # OOXML re-export barrel (snippet matching, formatting, validation)
│   ├── xml_snippet_matching.py # Core: snippet matching, XPath building, structural comparison
│   ├── xml_formatting.py      # OOXML formatting extraction and run building
│   ├── xml_validation.py      # OOXML element whitelist and well-formedness checks
│   ├── validators.py          # Shared input validation (file type, path safety, size limits)
│   └── verification.py        # Shared verification helpers (confidence counting, summaries)
├── tests/
│   ├── test_word.py
│   ├── test_word_verifier.py
│   ├── test_excel.py
│   ├── test_pdf.py
│   ├── test_xml_utils.py
│   └── fixtures/              # sample forms for testing
│       ├── table_questionnaire.docx
│       ├── placeholder_form.docx
│       ├── vendor_assessment.xlsx
│       ├── simple_form.pdf         # text fields, checkbox, dropdown
│       ├── multi_page_form.pdf     # fields across 3 pages
│       └── prefilled_form.pdf      # some fields already have values
└── docs/
    └── ARCHITECTURE.md
```

## Phased Build Order

### Phase 1: Word (.docx)
This is the hardest format and the most valuable. Focus here first.

1. `extract_structure_compact` — walk .docx body, assign element IDs, return compact indexed representation with id_to_xpath mapping
2. `extract_structure` — read .docx, return full `<w:body>` XML (alternative for large-context agents)
3. `validate_locations` — accept element IDs (fast XPath lookup) or OOXML snippets (snippet matching against document body)
4. `build_insertion_xml` — formatting inheritance and XML templating
5. `write_answers` — XPath-based insertion with replace/append/placeholder modes
6. `verify_output` — structural validation and content verification of filled documents
7. `list_form_fields` — heuristic detection of empty answer cells/placeholders

Key library: `lxml` for XML parsing and XPath. `python-docx` for high-level read/write when appropriate, but `lxml` directly for the OOXML manipulation.

### Phase 2: Excel (.xlsx)
Simpler than Word — no OOXML snippet matching needed, no insertion XML building.

1. `extract_structure_compact` — walk sheets/rows/cells, assign S1-R2-C3 IDs, detect formatting and merged cells
2. `extract_structure` — return JSON of sheets, rows, cells (raw representation)
3. `validate_locations` — confirm cell IDs exist and are within sheet bounds
4. `write_answers` — write values to cells using openpyxl (no insertion XML needed)
5. `verify_output` — read cell values and compare to expected answers
6. `list_form_fields` — detect Q/A column patterns and empty answer cells

Key library: `openpyxl`. No `build_insertion_xml` — openpyxl writes cell values directly.

### Phase 3: PDF (fillable AcroForm only)
Simplest format — PyMuPDF handles the heavy lifting. No OOXML manipulation, no insertion XML building. Uses `page.widgets()` to iterate native form widgets.

1. `extract_structure_compact` — walk all pages, iterate widgets, assign sequential F-IDs, extract nearby text (expand widget bounding box by ~100px, grab surrounding text for context), detect field types (text, checkbox, dropdown, radio, listbox), report current values and options
2. `extract_structure` — return full field list as JSON (same data as compact, structured form)
3. `validate_locations` — confirm field IDs exist in the F-ID mapping
4. `write_answers` — set widget values via PyMuPDF (text: set string, checkbox: coerce to bool, dropdown: validate against options, radio: set string), call `widget.update()` after each edit
5. `verify_output` — re-open filled PDF, read widget values, compare to expected (case-insensitive substring match)
6. `list_form_fields` — all AcroForm fields with types and current values (no nearby text)

Key library: `PyMuPDF` (fitz). No `build_insertion_xml` — PyMuPDF writes values directly via widget API. No `pypdfform` needed.

**Key design decisions (learned from Jerry Liu's `form_filling_app`):**
- **Sequential F-IDs instead of page+name composites** — avoids breakage with duplicate or empty field names
- **Nearby text extraction** — expand widget bounding box by ~100px, clip to page bounds, grab text with `page.get_text("text", clip=expanded_rect)` for AI context
- **No LLM calls** — return raw field names + nearby text + types; let the agent decide labels
- **Include field options** — for dropdowns/radio, show available options so the agent picks valid values
- **Include current values** — so the agent knows what to skip or overwrite
- **Graceful non-AcroForm handling** — if no widgets found, return clear message: "No fillable form fields found. This PDF may be a flat/scanned document."

**Edge cases to handle:**
1. Duplicate field names (same name on different pages) — F-IDs disambiguate
2. Read-only fields — report in compact output but skip during write
3. Very long field values — text overflow (set value, let PDF renderer handle display)
4. Non-AcroForm PDF (flat/scanned) — return empty field list with clear message
5. PDF with only checkboxes (no text fields)
6. Dropdown with value not in options list — return error for that specific field
7. Checkbox value coercion — convert "true"/"yes"/"1"/"checked" (case-insensitive) to bool

## Conventions

- Python 3.11+
- Type hints everywhere
- Pydantic for all data models (input/output of every tool)
- pytest for tests with fixtures
- lxml for all XML manipulation (not ElementTree)
- Each handler module exposes: extract_structure_compact(), extract_structure(), validate_locations(), build_insertion_xml() (Word only), write_answers(), verify_output(), list_form_fields()
- No LLM calls inside this server — ever
- Stateless — no persistent storage between calls
- All file I/O is bytes in, bytes out (or file_path in, file_path out)

## Vibe Coding Maintenance Principles

This project is maintained by a vibe coder — someone who uses AI to build and maintain code rather than writing it by hand. Every design decision must make it easy for an AI assistant (Claude Code, Copilot, etc.) to understand, modify, and extend the codebase in future sessions without context from previous ones.

### File size and structure
- No file longer than 200 lines. If a file grows beyond this, split it into focused modules.
- Each file does one thing and has a docstring at the top explaining what it does and why it exists.
- Each function does one thing and has a docstring explaining: what it takes, what it returns, and when you'd call it.
- No function longer than 40 lines. If it's longer, break it into named helper functions with clear names.

### Naming over comments
- Function and variable names should be self-explanatory. Prefer `find_snippet_in_body()` over `match()`.
- Comments explain WHY, not WHAT. The code tells you what; the comment tells you the reasoning or the gotcha.
- No abbreviations in public function names. `extract_structure` not `ext_struct`.

### No clever code
- Explicit is better than clever. No metaprogramming, no dynamic dispatch, no decorators that hide logic.
- No deep inheritance. Flat is better than nested.
- If a pattern appears twice, that's fine. If it appears three times, extract it into a clearly named helper.
- Prefer simple if/else over complex comprehensions or chained operations.

### Dependency between files
- Each module should be understandable in isolation. A future AI session should be able to read one file and know what it does without reading the whole codebase.
- Import dependencies should flow one way: server.py → handlers → xml_utils/validators → models. Never circular.
- Shared constants (namespaces, field types, etc.) live in one place and are imported everywhere else.

### Tests as documentation
- Each test file mirrors the source file it tests.
- Test function names describe the scenario: `test_validate_locations_returns_not_found_for_missing_snippet`.
- Tests are the first thing a new AI session should read to understand what a module does.
- If a bug is fixed, a test is added that would have caught it.

### Change safety
- Before changing any function, run its tests. After changing it, run them again.
- If a change touches xml_utils.py, run all tests — other modules depend on it.
- Never change a function signature without updating all callers and their tests.
- Each commit should leave all tests passing. No "will fix later" commits.

## OOXML Namespace Handling

Word OOXML uses namespaces extensively. Always register them:

```python
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
}
```

All XPath queries must use these prefixes. Snippet matching should normalise whitespace and handle namespace prefix variations.

## What NOT to Build

- No web UI or REST API (MCP only)
- No Docker
- No database or persistent storage
- No authentication
- No LLM/AI integration inside the server
- No file watching or background processes
- No image-based form detection (only structured documents)
- No non-fillable PDF support (no OCR, no image PDFs)

## Agent Guidance

Recommended practices for copilot agents using these MCP tools:

### Use the right tool for the right document
- **MCP tools** (`extract_structure_compact`, `validate_locations`, `write_answers`, etc.) are exclusively for operating on the **form being filled** — the questionnaire, the application, the assessment.
- **Reference/knowledge documents** (company policies, previous questionnaires, knowledge bases) should be read using the agent's own native file tools (e.g. `Read`, file upload, attached context). Do not pass knowledge documents to MCP tools.

### Handle large answer sets efficiently
- For small payloads (up to ~20 answers), pass answers inline to `write_answers`.
- For large payloads (>20 answers), write the answers array to a JSON file on disk and use `answers_file_path`. This avoids generating enormous tool-call parameters that overwhelm the agent's context window.

### Assess confidence honestly
- For each question, assess whether the knowledge source contains relevant information.
- If it does, include the answer with confidence `"known"`.
- If you can reasonably infer an answer but are not certain, mark it `"uncertain"`.
- If you cannot answer, mark it `"unknown"` and **do not include it in the `write_answers` call** — leave the cell empty so the user can fill it manually.
- After the pipeline completes, report all unknown questions to the user so they can fill those manually.

### Batch if context-constrained
- If the form has many questions and the agent's context window is limited, process sections in batches: extract → identify → validate → write for each batch.

## Testing Strategy

- Create realistic fixture files for each document type
- Word fixture 1: two-column table questionnaire (question | answer)
- Word fixture 2: paragraph form with placeholder text like "[Enter here]" and "___"
- Word fixture 3: mixed layout (tables + paragraphs + headers)
- Excel fixture: vendor assessment with header row and Q/A columns
- PDF fixture 1: simple form with text fields, checkbox, dropdown
- PDF fixture 2: multi-page form with fields across 3 pages
- PDF fixture 3: pre-filled form with some fields already populated
- Test each handler function independently
- Test the full pipeline: extract → validate → build → write → verify
- Validate that written documents open correctly in Word/Excel/Acrobat
- Validate that formatting is preserved after writing

## Dependencies

```
mcp
lxml
python-docx
openpyxl
pymupdf
pydantic
pytest
```
