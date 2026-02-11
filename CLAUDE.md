# Form Filler MCP Server

## What This Is

An MCP server that exposes form-filling tools for copilot agents. It handles the deterministic side of form filling — reading document structure, validating locations, building insertion XML, and writing answers back. The calling agent handles all AI reasoning (identifying pairs, generating answers). This server never makes LLM calls.

The typical use case: a company sets up a copilot agent with its institutional knowledge already loaded (company policies, previous questionnaires, standard answers, corporate data). When a user receives a questionnaire, they drop it into the agent. The agent calls this MCP server to extract the form structure, identifies the questions, draws on its own knowledge plus any user instructions ("our D&O coverage is $10M", "use the London office address") to generate answers, then calls the server again to write those answers back into the document.

The MCP server's job is strictly document manipulation. All knowledge — institutional and ad-hoc — lives with the agent.

Starts with Word (.docx), then Excel (.xlsx), then PDF (fillable forms).

## Core Design Principle

AI is good at reading OOXML and understanding what it means. AI is bad at writing large amounts of correct OOXML from scratch. So we split the work:

- **AI reads** the full OOXML and identifies question/answer pairs
- **AI returns** each answer location as a small OOXML snippet (a locator)
- **Code validates** that each snippet actually exists in the document
- **AI answers** the questions using the agent's institutional knowledge and user instructions (plain text only, no OOXML)
- **Code builds** the insertion OOXML (for plain text answers) or **AI builds** a small OOXML snippet (for structured answers like checkboxes)
- **Code validates** any AI-generated insertion XML is well-formed
- **Code writes** the answer into the document at the located position

The MCP server owns steps: validate locations, build plain insertion XML, validate insertion XML, and write. The calling agent owns: identify pairs, generate answers (using its own knowledge + user instructions), and optionally build structured insertion XML.

## The Pipeline

```
STEP 1: EXTRACT STRUCTURE (MCP tool — deterministic)
  Input:  form document bytes, file type
  Output: full OOXML body as text (for Word), or structured representation
  Note:   the calling agent sends this to AI for pair identification

STEP 2: VALIDATE LOCATIONS (MCP tool — deterministic)
  Input:  document bytes, array of OOXML location snippets from AI
  Output: validated array with match status and XPath for each snippet
  Action: confirms each snippet exists in the document body
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
```

### Where Knowledge Lives

The MCP server has no knowledge layer. All knowledge sits with the copilot agent:

- **Institutional knowledge** — loaded when the agent is configured (company policies, standard answers, corporate data, previous questionnaires). This is the agent's built-in context.
- **User instructions** — provided at runtime ("our CEO is Jane Smith", "coverage limit is $10M"). The agent receives these directly.
- **Additional documents** — if the user attaches reference files alongside the form, the agent can read them using its own file handling. The MCP server provides an optional `extract_text` utility to help parse non-trivial formats, but this is a convenience, not a core pipeline step.

The agent combines all three sources when generating answers. The MCP server only sees the form document itself.

### How the Calling Agent Orchestrates This

```
1. User drops in: form document + optional instructions
2. Agent calls extract_structure → gets form structure
3. Agent sends form structure to AI → gets question/location pairs
   (AI uses agent's institutional knowledge to understand context)
4. Agent calls validate_locations → confirms locations are real
5. Agent generates answers using: institutional knowledge + user instructions
6. Agent calls build_insertion_xml for each answer → gets OOXML to insert
7. Agent calls write_answers → gets completed document
```

## MCP Tools

### `extract_structure(file_bytes, file_type) → document structure`

Returns the raw OOXML body (Word) or structured representation (Excel/PDF) so the calling agent can send it to AI for pair identification.

For Word: returns the full `<w:body>` XML as a string. The calling agent sends this to AI with a prompt like "identify question/answer pairs and return each answer location as an OOXML snippet."

For Excel: returns a JSON representation of sheets, rows, columns, merged cells, and cell values.

For PDF: returns a list of fillable field names, types, and current values.

### `extract_text(file_bytes, file_type) → text content` *(optional utility)*

A convenience tool for when the agent needs to read an attached document that isn't the form itself — for example, if the user drops in a reference PDF alongside the questionnaire. Extracts plain text from Word, Excel, PDF, or TXT files.

This is not part of the core pipeline. Most copilot agents can read files natively. This tool exists for agents that cannot, or for non-trivial formats where python-docx/openpyxl/PyMuPDF would do a better job than the agent's built-in file reader.

### `validate_locations(file_bytes, file_type, locations[]) → validated_locations[]`

Each location is an OOXML snippet (Word), cell reference (Excel), or field name (PDF).

For Word: searches the document XML for each snippet. Returns match/no-match and the XPath to the matched element. Handles minor whitespace differences. Flags ambiguous matches (snippet appears more than once).

For Excel: confirms cell references exist and are within sheet bounds.

For PDF: confirms field names exist in the form.

Returns:
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

For PDF: not needed — PyPDFForm fills fields by name.

### `write_answers(file_bytes, file_type, answers[]) → filled_file_bytes`

Each answer is:
```json
{
  "pair_id": "q1",
  "xpath": "/w:body/w:tbl[2]/w:tr[3]/w:tc[2]/w:p[1]",
  "insertion_xml": "<w:r><w:rPr><w:rFonts w:ascii='Calibri'/><w:sz w:val='22'/></w:rPr><w:t>Answer text here</w:t></w:r>",
  "mode": "replace_content"
}
```

Modes:
- `replace_content` — clears existing content in the target element, inserts new
- `append` — adds after existing content
- `replace_placeholder` — finds placeholder text (e.g. "[Enter here]") within the target and replaces only that

Returns the complete document as bytes with all answers inserted.

### `list_form_fields(file_bytes, file_type) → fields[]`

A simpler utility. Returns a plain inventory of all fillable targets found by code (not AI). For Word: empty table cells following a cell with text, paragraphs containing common placeholders. For Excel: empty cells adjacent to cells with question-like text. For PDF: named form fields.

## Project Structure

```
vibe-legal-form-filler/
├── CLAUDE.md
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── server.py              # MCP server entry point, tool registration
│   ├── models.py              # Pydantic models for pairs, locations, answers
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── word.py            # Word handler: extract, validate, build XML, write
│   │   ├── excel.py           # Excel handler: extract, validate, write
│   │   ├── pdf.py             # PDF handler: extract, validate, write
│   │   └── text_extractor.py  # Optional: extract plain text from any supported format
│   ├── xml_utils.py           # OOXML snippet matching, XPath resolution,
│   │                          #   formatting inheritance, well-formedness checks
│   └── validators.py          # Shared validation logic
├── tests/
│   ├── test_word.py
│   ├── test_excel.py
│   ├── test_pdf.py
│   ├── test_xml_utils.py
│   └── fixtures/              # sample forms for testing
│       ├── table_questionnaire.docx
│       ├── placeholder_form.docx
│       ├── vendor_assessment.xlsx
│       └── fillable_application.pdf
└── docs/
    └── ARCHITECTURE.md
```

## Phased Build Order

### Phase 1: Word (.docx)
This is the hardest format and the most valuable. Focus here first.

1. `extract_structure` — read .docx, return full `<w:body>` XML
2. `validate_locations` — OOXML snippet matching against document body
3. `build_insertion_xml` — formatting inheritance and XML templating
4. `write_answers` — XPath-based insertion with replace/append/placeholder modes
5. `list_form_fields` — heuristic detection of empty answer cells/placeholders

Key library: `lxml` for XML parsing and XPath. `python-docx` for high-level read/write when appropriate, but `lxml` directly for the OOXML manipulation.

### Phase 2: Excel (.xlsx)
Simpler than Word — no OOXML snippet matching needed.

1. `extract_structure` — return JSON of sheets, rows, cells
2. `validate_locations` — confirm cell references exist
3. `write_answers` — write values to cells using openpyxl
4. `list_form_fields` — detect Q/A column patterns

Key library: `openpyxl`.

### Phase 3: PDF (fillable forms only)
Simplest format — named fields with known types.

1. `extract_structure` — return list of field names, types, current values
2. `validate_locations` — confirm field names exist
3. `write_answers` — fill fields by name
4. `list_form_fields` — same as extract_structure for PDF

Key library: `PyPDFForm` or `PyMuPDF`.

## Conventions

- Python 3.11+
- Type hints everywhere
- Pydantic for all data models (input/output of every tool)
- pytest for tests with fixtures
- lxml for all XML manipulation (not ElementTree)
- Each handler module exposes: extract_structure(), validate_locations(), build_insertion_xml() (Word only), write_answers(), list_form_fields()
- No LLM calls inside this server — ever
- Stateless — no persistent storage between calls
- All file I/O is bytes in, bytes out

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

## Testing Strategy

- Create realistic fixture files for each document type
- Word fixture 1: two-column table questionnaire (question | answer)
- Word fixture 2: paragraph form with placeholder text like "[Enter here]" and "___"
- Word fixture 3: mixed layout (tables + paragraphs + headers)
- Excel fixture: vendor assessment with header row and Q/A columns
- PDF fixture: fillable form with text fields, checkboxes, dropdowns
- Test each handler function independently
- Test the full pipeline: extract → validate → build → write
- Validate that written documents open correctly in Word/Excel/Acrobat
- Validate that formatting is preserved after writing

## Dependencies

```
mcp
lxml
python-docx
openpyxl
pypdfform
pymupdf
pydantic
pytest
```
