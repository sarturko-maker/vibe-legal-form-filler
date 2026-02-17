# Claude Code Setup (stdio)

Claude Code connects to the MCP server using **stdio transport**. The server runs as a subprocess managed by Claude Code -- no separate server process is needed.

## Configuration

Place a `.mcp.json` file at the project root:

```json
{
  "mcpServers": {
    "form-filler": {
      "command": ".venv/bin/python",
      "args": ["-m", "src.server"]
    }
  }
}
```

This tells Claude Code to:

1. Start `.venv/bin/python -m src.server` as a subprocess
2. Communicate with it over stdin/stdout (stdio transport)
3. Register the server under the name `form-filler`

No `--transport` flag is needed -- stdio is the default.

## Verification

Claude Code automatically discovers tools from `.mcp.json` when you open the project directory. To confirm the server is connected and tools are available:

1. Open the project directory in Claude Code
2. Claude Code will start the MCP server subprocess automatically
3. Ask Claude to use a form-filler tool (e.g., "extract the structure of tests/fixtures/table_questionnaire.docx")
4. Claude should call the `extract_structure_compact` tool and return results

If tools are not available, check that:

- The `.mcp.json` file is at the project root (not inside `src/` or another subdirectory)
- The virtual environment exists at `.venv/` with all dependencies installed
- The server starts without errors: `.venv/bin/python -m src.server` (should hang waiting for stdio input, press `Ctrl+C` to exit)

## Available Tools

The server registers 7 tools:

| Tool | Purpose |
|------|---------|
| `extract_structure_compact` | Extract a compact, indexed representation of a form document (Word, Excel, PDF) |
| `extract_structure` | Extract the raw document structure (full OOXML for Word, structured JSON for Excel/PDF) |
| `validate_locations` | Confirm that element IDs or OOXML snippets map to real locations in the document |
| `build_insertion_xml` | Build well-formed OOXML for inserting an answer into a Word document |
| `write_answers` | Write answers into a form document at validated locations |
| `verify_output` | Verify that answers were written correctly and the document structure is valid |
| `list_form_fields` | List all detected fillable targets in a form document |

## Notes

- Claude Code uses **stdio transport only**. HTTP configuration is not needed and not supported by Claude Code.
- The server is stateless -- each tool call is independent. No session management is required.
- This is the existing, working configuration from the project's initial setup. No changes are needed to use the server with Claude Code.
- The `.mcp.json` file is already committed to the repository.
