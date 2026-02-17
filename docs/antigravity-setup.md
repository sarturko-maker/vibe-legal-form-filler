# Antigravity Setup (HTTP)

Antigravity connects to the MCP server using **Streamable HTTP transport**. Unlike stdio (where the client spawns the server), HTTP requires the server to be running before Antigravity connects.

## Prerequisites

1. **Antigravity installed** (v1.0 or later for Streamable HTTP support)
2. **HTTP server running** -- see [HTTP Transport](http-transport.md) for how to start the server

Start the server in a separate terminal before proceeding:

```bash
python -m src.server --transport http
# Wait for: INFO:  Uvicorn running on http://127.0.0.1:8000
```

## Configuration

Edit `~/.gemini/antigravity/mcp_config.json` and add the `form-filler-http` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "form-filler-http": {
      "serverUrl": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

**Important:** Use `serverUrl` -- not `httpUrl` or `url`. Antigravity uses a different key name than Gemini CLI. Using the wrong key will silently fail to connect.

If the file does not exist, create it with the content above. If it already exists with other MCP servers, add the `form-filler-http` entry alongside them.

## Verification

1. Start the HTTP server (if not already running)
2. Open Antigravity
3. Click the **"..."** (three-dot menu) in the Agent panel
4. Select **"MCP Servers"**
5. Confirm that `form-filler-http` appears in the list with tools displayed:
   - `extract_structure_compact`
   - `extract_structure`
   - `validate_locations`
   - `build_insertion_xml`
   - `write_answers`
   - `verify_output`
   - `list_form_fields`
6. Click **"Manage MCP Servers"** to see detailed status and tool descriptions

If the server does not appear, try clicking the refresh button or restarting Antigravity.

## Running the Pipeline

Open the project directory in Antigravity and use this prompt in the agent interface:

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

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Server not listed in MCP Servers panel | Server is not running | Start the HTTP server first: `python -m src.server --transport http` |
| Server appears but shows no tools | Using `httpUrl` instead of `serverUrl` | Change the key to `serverUrl` in mcp_config.json |
| "Not Found" or 404 errors | Missing `/mcp` path in URL | Use `http://127.0.0.1:8000/mcp`, not `http://127.0.0.1:8000` |
| Tool calls hang indefinitely | Known issue (FastMCP #2489) | Restart Antigravity. If persistent, check server logs for errors |
| Server not connecting after config change | Stale config | Click refresh in MCP Servers panel, or restart Antigravity |
| Connection refused | Wrong port or server not running | Verify the server is running and the port matches your config |
