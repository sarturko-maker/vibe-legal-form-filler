# Gemini CLI Setup (HTTP)

Gemini CLI connects to the MCP server using **Streamable HTTP transport**. Unlike stdio (where the client spawns the server), HTTP requires the server to be running before Gemini CLI connects.

## Prerequisites

1. **Gemini CLI installed** (v0.1.16 or later for Streamable HTTP support)
2. **HTTP server running** -- see [HTTP Transport](http-transport.md) for how to start the server

Start the server in a separate terminal before proceeding:

```bash
python -m src.server --transport http
# Wait for: INFO:  Uvicorn running on http://127.0.0.1:8000
```

## Configuration

Two options for adding the HTTP MCP server to Gemini CLI:

### Option A: CLI command (recommended)

```bash
gemini mcp add --transport http --trust form-filler-http http://127.0.0.1:8000/mcp
```

This writes the configuration to `~/.gemini/settings.json` automatically.

### Option B: Manual settings.json edit

Edit `~/.gemini/settings.json` and add the `form-filler-http` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "form-filler-http": {
      "httpUrl": "http://127.0.0.1:8000/mcp",
      "trust": true
    }
  }
}
```

**Important:** Use `httpUrl` -- not `url`. The `url` key is for the deprecated SSE transport and will not work with Streamable HTTP.

The `trust: true` setting bypasses per-tool confirmation prompts, which is useful during testing.

## Verification

1. Start the HTTP server (if not already running)
2. Launch Gemini CLI:
   ```bash
   gemini
   ```
3. Run the `/mcp` command inside the Gemini CLI session:
   ```
   /mcp
   ```
4. Expected output: `form-filler-http` shows **CONNECTED** with 7 tools listed:
   - `extract_structure_compact`
   - `extract_structure`
   - `validate_locations`
   - `build_insertion_xml`
   - `write_answers`
   - `verify_output`
   - `list_form_fields`

## Running the Pipeline

Use this prompt to run the full MCP pipeline through Gemini CLI:

```
I have a Word questionnaire at tests/fixtures/table_questionnaire.docx.
Using the MCP form-filler tools:
1. Call extract_structure_compact with file_path="tests/fixtures/table_questionnaire.docx"
2. From the compact_text, identify a few question/answer pairs
3. Call validate_locations to confirm the element IDs are valid
4. Call build_insertion_xml for each answer with plain text
5. Call write_answers to fill in the answers (use output_file_path="/tmp/filled_questionnaire.docx")
6. Call verify_output to confirm the answers were written correctly

Show me the results at each step.
```

The agent should call each tool sequentially and report the results. The filled document will be written to `/tmp/filled_questionnaire.docx`.

## Stdio vs HTTP Conflict

If you have both a stdio server (`form-filler`) and an HTTP server (`form-filler-http`) configured, Gemini CLI may prefix tool names with the server name to avoid conflicts (e.g., `form_filler_http__extract_structure_compact`).

To avoid this, disable the stdio server when testing HTTP:

```bash
gemini mcp disable form-filler
```

Re-enable it later with:

```bash
gemini mcp enable form-filler
```

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "Disconnected" in `/mcp` output | Server is not running | Start the HTTP server first: `python -m src.server --transport http` |
| "Not Found" or 404 errors | Missing `/mcp` path in URL | Use `http://127.0.0.1:8000/mcp`, not `http://127.0.0.1:8000` |
| Tools not discovered | Using `url` instead of `httpUrl` | Change the key to `httpUrl` in settings.json |
| Tool names are prefixed | Both stdio and HTTP servers active | Disable the stdio server: `gemini mcp disable form-filler` |
| `FatalAuthenticationError` | Running from non-interactive terminal | Run Gemini CLI from an interactive terminal for OAuth |
| Connection refused | Wrong port or server not running | Verify the server is running and the port matches your config |
