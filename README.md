# Vibe Legal Form Filler

MCP server for AI-powered form filling across Word, Excel, and PDF documents.

## Vibe Coded

This project was built entirely through "vibe coding" — an AI-assisted development approach where a non-programmer designed the architecture and directed implementation using AI tools. No line of code was written manually. The author is not a software engineer and makes no representations about code quality.

## What It Does

Vibe Legal Form Filler provides deterministic document manipulation tools — extract structure, validate locations, write answers, and verify output — that any AI agent can orchestrate via the [MCP protocol](https://modelcontextprotocol.io/).

The server handles the hard parts of document parsing (OOXML, spreadsheet cells, AcroForm fields) and returns compact, human-readable representations with stable element IDs. The calling agent handles all reasoning: identifying questions, generating answers from its own knowledge, and deciding what to write where.

### The Pipeline

```
1. extract_structure_compact  →  compact indexed representation (a few KB, not 134KB)
2. validate_locations         →  confirm element IDs map to real document locations
3. build_insertion_xml        →  well-formed OOXML for Word (not needed for Excel/PDF)
4. write_answers              →  insert answers into the document
5. verify_output              →  structural validation + content verification
```

## Key Design Principles

- **No LLM in the server** — The server is a deterministic document tool, not an AI model. It reads, writes, and verifies — reliably and repeatably. The AI agent you already use (Claude, Gemini, Copilot, etc.) provides the intelligence and orchestrates the pipeline.
- **Agent-agnostic** — works with any copilot agent that speaks MCP (Claude, GPT, custom agents).
- **Privacy-first (BYOK)** — no data leaves the server. Your documents, your agent, your knowledge.
- **Format-agnostic pipeline** — the same extract → validate → write → verify flow works across all supported formats.

## Supported Formats

| Format | Library | Notes |
|--------|---------|-------|
| **Word** (.docx) | lxml, python-docx | Full OOXML manipulation, formatting inheritance, content controls |
| **Excel** (.xlsx) | openpyxl | Cell-level read/write, merged cell detection, multi-sheet support |
| **PDF** (.pdf) | PyMuPDF | Fillable AcroForm fields only (text, checkbox, dropdown, radio) |

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run as MCP Server

```bash
python -m src.server
```

Or add to your MCP client configuration:

```json
{
  "mcpServers": {
    "form-filler": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/vibe-legal-form-filler"
    }
  }
}
```

### Run Tests

```bash
pytest
```

## How Agents Use This

```
1. User drops in: form document + optional knowledge documents + instructions
2. Agent calls extract_structure_compact(file_path="form.docx")
3. Agent reads knowledge docs using its own file tools (not MCP)
4. Agent identifies Q/A pairs from the compact representation
5. Agent calls validate_locations → confirms IDs are real
6. Agent generates answers using its knowledge + user instructions
7. Agent calls write_answers → filled document written to disk
8. Agent calls verify_output → confirms all answers landed correctly
9. Agent reports unknown questions to the user for manual completion
```

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).

Any modifications or derivative works must be shared under the same license. If you run a modified version of this server as a network service, you must make the source code available to users of that service.

Dual licensing available on request — see [NOTICE](NOTICE).

## Disclaimer

This software is provided as-is, without warranty of any kind. It is an experimental tool built through AI-assisted development. Users should independently verify all outputs before relying on them for any purpose. The author accepts no liability for errors, omissions, or any consequences arising from use of this software. This disclaimer applies in addition to the terms of the AGPL-3.0 license.
