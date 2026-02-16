# External Integrations

**Analysis Date:** 2025-02-16

## APIs & External Services

**None configured.**

This server does not integrate with any external APIs or services. All document processing is self-contained using Python libraries. The server is designed to run offline with no network dependencies.

## Data Storage

**Databases:**
- None — stateless operation
- No persistent storage between MCP tool calls
- Each tool call is independent

**File Storage:**
- Local filesystem only
- Input: file_path (absolute or relative path on disk) or file_bytes_b64 (base64-encoded bytes)
- Output: bytes returned or written to output_file_path on disk
- Temporary I/O: BytesIO objects used for ZIP operations (.docx, .xlsx are ZIP containers)

**Caching:**
- None — no caching layer
- Each document processing is stateless

## Authentication & Identity

**Auth Provider:**
- None configured
- Server assumes calling agent is trusted
- No API keys, no tokens, no credential files

## Monitoring & Observability

**Error Tracking:**
- None — no external error reporting
- Errors raised as exceptions caught by calling MCP client

**Logs:**
- None — no external logging service
- All output to stdout/stderr (captured by MCP transport)
- No structured logging configuration

## CI/CD & Deployment

**Hosting:**
- Runs locally as an MCP server connected via stdio
- No cloud hosting configured
- No deployment pipeline (manual setup via calling agent's MCP client config)

**CI Pipeline:**
- None configured — no GitHub Actions, GitLab CI, or equivalent
- Tests run locally via pytest: `pytest tests/`

## Environment Configuration

**Required env vars:**
- None — server is configuration-free
- No secrets to set up
- No API endpoints to configure
- No database credentials

**Secrets location:**
- None — no secrets used
- .env files ignored by default (.gitignore includes .env and .env.local)

## Webhooks & Callbacks

**Incoming:**
- None — server is stateless and passive
- Only receives synchronous MCP tool calls from calling agent

**Outgoing:**
- None — server never initiates outbound connections
- No callbacks to external services
- No webhook registrations

## Protocol Interfaces

**MCP (Model Context Protocol):**
- Version: 1.26.0+
- Transport: stdio (standard input/output)
- Server name: "form-filler"
- Tools exposed: 7 read-only tools + 2 write tools (see below)

**Extract/Read Tools:**
- `extract_structure_compact(file_path | file_bytes_b64, file_type?)` → compact indexed representation
- `extract_structure(file_path | file_bytes_b64, file_type?)` → raw document structure
- `validate_locations(file_path | file_bytes_b64, file_type?, locations[])` → validated location mappings
- `build_insertion_xml(answer_text, target_context_xml, answer_type)` → well-formed OOXML
- `list_form_fields(file_path | file_bytes_b64, file_type?)` → inventory of fillable fields

**Write Tools:**
- `write_answers(file_path | file_bytes_b64, file_type?, answers[] | answers_file_path?, output_file_path?)` → filled document
- `verify_output(file_path | file_bytes_b64, file_type?, expected_answers[])` → structural + content verification

**Input/Output Formats:**
- JSON (MCP protocol) for all tool parameters and responses
- Binary bytes (base64-encoded for transport, raw bytes for file I/O)
- OOXML XML strings for Word document fragments
- Pydantic model serialization to JSON

## File Format Support

**Supported for extraction, validation, writing, verification:**
- `.docx` (Word 2007+) — OOXML format, ZIP-based, parsed via lxml
- `.xlsx` (Excel 2007+) — ECMA-376 format, ZIP-based, parsed via openpyxl
- `.pdf` (Fillable AcroForm only) — read/write via PyMuPDF widget API

**Not supported:**
- Flat/scanned PDFs (no OCR)
- Legacy formats (.doc, .xls, .rtf)
- OpenDocument formats (.odt, .ods)
- Encrypted/password-protected documents (will error on read)

## Data Flow

1. **Calling agent** (Claude, GPT, custom) has MCP client configured to spawn this server
2. **Agent** calls MCP tool (e.g., `extract_structure_compact`) with document path or base64 bytes
3. **Server** processes document using lxml, openpyxl, or PyMuPDF
4. **Server** returns JSON response with extracted structure, element IDs, validation results, or filled bytes
5. **Agent** processes response (no network round-trip)
6. **Agent** calls next tool in pipeline (validate, write, verify)

**Critical design point:** No data is sent to external services. All processing is local. The agent's institutional knowledge and user instructions remain on the agent side — the server only sees the form document being filled.

---

*Integration audit: 2025-02-16*
