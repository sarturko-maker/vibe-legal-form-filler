# Phase 4: Cross-Platform Verification - Research

**Researched:** 2026-02-16
**Domain:** Cross-platform MCP client configuration (Gemini CLI, Antigravity IDE), manual integration testing, setup documentation
**Confidence:** HIGH

## Summary

Phase 4 is a verification and documentation phase, not a coding phase. The server is already fully functional over HTTP (Phases 1-3 complete, 234 tests passing, endpoint at `http://127.0.0.1:8000/mcp`). The work is: (1) configure Gemini CLI and Antigravity to connect to the HTTP server, (2) manually run the full pipeline through each platform, (3) document the setup procedures so a future user can replicate them.

Both platforms are already installed on this Chromebook. Gemini CLI v0.28.2 is available at `/home/sarturko/.config/nvm/versions/node/v20.19.6/bin/gemini` and already has the form-filler configured in stdio mode in `~/.gemini/settings.json`. Antigravity v1.15.8 is installed at `/usr/bin/antigravity` with its MCP config at `~/.gemini/antigravity/mcp_config.json`. Both platforms support Streamable HTTP transport natively. The key difference: Gemini CLI uses `httpUrl` for HTTP endpoints while Antigravity uses `serverUrl`.

The server exposes 7 MCP tools (6 core + `list_form_fields`). The endpoint is `/mcp` (verified). Test fixtures exist for all three document types (Word, Excel, PDF). No new code is needed -- this phase is purely configuration, testing, and documentation.

**Primary recommendation:** Start the HTTP server in one terminal (`python -m src.server --transport http`), then configure each platform to connect to `http://127.0.0.1:8000/mcp`. Verify tool discovery with `/mcp` command (Gemini CLI) or MCP Servers panel (Antigravity). Run the full pipeline with `table_questionnaire.docx` as the sample form. Document every step with exact commands and config snippets.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| XPLAT-01 | Gemini CLI successfully connects to the server and discovers all tools | Gemini CLI v0.28.2 installed, supports `httpUrl` for Streamable HTTP. Config: `{"httpUrl": "http://127.0.0.1:8000/mcp"}` in `~/.gemini/settings.json`. Verify with `/mcp` command inside Gemini CLI session. Server exposes 7 tools via `/mcp` endpoint. |
| XPLAT-02 | Gemini CLI completes a full questionnaire pipeline (extract -> validate -> build XML -> write -> verify) | Pipeline uses 5 sequential tool calls with `table_questionnaire.docx`. Gemini CLI calls MCP tools natively -- agent drives the pipeline. `trust: true` bypasses per-tool confirmation prompts for faster testing. |
| XPLAT-03 | Antigravity successfully connects to the server and discovers all tools | Antigravity v1.15.8 installed. Config: `{"serverUrl": "http://127.0.0.1:8000/mcp"}` in `~/.gemini/antigravity/mcp_config.json`. Verify via MCP Servers panel (three-dot menu -> MCP Servers). Note: Antigravity uses `serverUrl`, NOT `httpUrl`. |
| XPLAT-04 | Antigravity completes a full questionnaire pipeline (extract -> validate -> build XML -> write -> verify) | Same pipeline as XPLAT-02 but driven by Antigravity's agent. Open the project directory in Antigravity, ensure MCP server is connected, then prompt the agent to fill a form using the MCP tools. |
| DOCS-01 | HTTP transport usage documentation (how to start, port configuration, transport flag) | Document: `python -m src.server --transport http` (default port 8000), `--port` flag, `--host` flag, env var fallbacks (`MCP_FORM_FILLER_TRANSPORT`, `MCP_FORM_FILLER_PORT`, `MCP_FORM_FILLER_HOST`). Refer to existing `server.py` CLI for exact flags. |
| DOCS-02 | Claude Code setup guide (stdio -- existing config, confirm still works) | Existing `.mcp.json` at project root already works: `{"mcpServers": {"form-filler": {"command": ".venv/bin/python", "args": ["-m", "src.server"]}}}`. Gemini CLI also has a stdio config. Confirm both still work after HTTP code changes. |
| DOCS-03 | Gemini CLI setup guide (connection config, tested commands) | Document: `gemini mcp add --transport http form-filler-http http://127.0.0.1:8000/mcp --trust` OR manual `settings.json` edit. Include `/mcp` verification command and the full pipeline prompt. |
| DOCS-04 | Antigravity setup guide (connection config, tested commands) | Document: Edit `~/.gemini/antigravity/mcp_config.json` with `serverUrl` key. Include MCP Servers panel verification steps and the full pipeline prompt. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Gemini CLI | 0.28.2 | MCP client for terminal-based AI agent | Already installed. Supports Streamable HTTP via `httpUrl` in settings.json. Google's official CLI for Gemini. |
| Antigravity IDE | 1.15.8 | MCP client for IDE-based AI agent | Already installed. Supports Streamable HTTP via `serverUrl` in mcp_config.json. Google's agent-first IDE. |
| Claude Code | (current) | MCP client for terminal-based AI agent (stdio) | Already working. Uses `.mcp.json` at project root. Stdio transport only. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Node.js | 20.19.6 | Runtime for Gemini CLI | Already installed via nvm. Required for `gemini` command. |
| npm | 11.9.0 | Package manager (Gemini CLI installed globally) | Already available. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual settings.json edit for Gemini CLI | `gemini mcp add --transport http` CLI command | CLI command is faster but manual edit is more explicit for documentation. Use CLI command for speed, document both. |
| Antigravity serverUrl config | Antigravity command/stdio config | HTTP is the whole point of this milestone. Stdio works but doesn't test HTTP. |

**Installation:**
No new packages needed. Both platforms already installed on the Chromebook.

## Architecture Patterns

### Recommended Documentation Structure
```
docs/
├── http-transport.md       # DOCS-01: HTTP transport usage
├── claude-code-setup.md    # DOCS-02: Claude Code (stdio) setup
├── gemini-cli-setup.md     # DOCS-03: Gemini CLI (HTTP) setup
└── antigravity-setup.md    # DOCS-04: Antigravity (HTTP) setup
```

### Pattern 1: Two-Terminal Testing Setup
**What:** Start the HTTP server in terminal 1, run the MCP client in terminal 2.
**When to use:** For all manual cross-platform verification (XPLAT-01 through XPLAT-04).
**Why:** The HTTP server must be running before the client can connect. Terminal 1 shows server logs (uvicorn output), terminal 2 shows client interaction.
```bash
# Terminal 1: Start HTTP server
cd /home/sarturko/vibe-legal-form-filler
python -m src.server --transport http
# Output: INFO: Uvicorn running on http://127.0.0.1:8000

# Terminal 2: Connect client
gemini  # Then use /mcp to verify tools
```
**Verified:** Server binds to 127.0.0.1:8000, endpoint is `/mcp`.

### Pattern 2: Gemini CLI HTTP Configuration
**What:** Add the form-filler server as an HTTP transport MCP server in Gemini CLI settings.
**When to use:** XPLAT-01 and XPLAT-02.
```json
// In ~/.gemini/settings.json, add alongside existing stdio config:
{
  "mcpServers": {
    "form-filler": {
      "command": "uv",
      "args": ["run", "--directory", "/home/sarturko/vibe-legal-form-filler", "python", "-m", "src.server"],
      "trust": true
    },
    "form-filler-http": {
      "httpUrl": "http://127.0.0.1:8000/mcp",
      "trust": true
    }
  }
}
```
**Key details:**
- `httpUrl` (NOT `url`) -- `url` is for SSE transport, `httpUrl` is for Streamable HTTP
- `trust: true` -- bypasses tool-call confirmation prompts during testing
- Keep the existing stdio `form-filler` entry alongside the HTTP one for comparison
- Tool names may get prefixed if both stdio and HTTP servers are connected (conflict resolution)
- Default timeout is 600,000ms (10 min), more than enough for form operations

**CLI alternative:**
```bash
gemini mcp add --transport http --trust form-filler-http http://127.0.0.1:8000/mcp
```
**Verified:** `gemini mcp add --help` confirms `--transport http` and `--trust` flags available.

### Pattern 3: Antigravity HTTP Configuration
**What:** Add the form-filler server as an HTTP transport MCP server in Antigravity config.
**When to use:** XPLAT-03 and XPLAT-04.
```json
// In ~/.gemini/antigravity/mcp_config.json:
{
  "mcpServers": {
    "form-filler-http": {
      "serverUrl": "http://127.0.0.1:8000/mcp"
    }
  }
}
```
**Key details:**
- `serverUrl` (NOT `httpUrl` or `url`) -- Antigravity uses a different key name than Gemini CLI
- No `trust` equivalent documented -- Antigravity may prompt for tool confirmation
- After editing, click refresh in MCP Servers panel, or restart Antigravity
- Config location: `~/.gemini/antigravity/mcp_config.json` (verified directory exists on this machine)

### Pattern 4: Pipeline Verification Prompt
**What:** A prompt that instructs the AI agent to run the full MCP pipeline.
**When to use:** XPLAT-02 and XPLAT-04 (full pipeline tests).
**Why:** The MCP server provides tools; the agent orchestrates them. The prompt must tell the agent what to do.
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

### Anti-Patterns to Avoid
- **Testing with server not running:** The HTTP server must be started BEFORE connecting Gemini CLI or Antigravity. Unlike stdio (which spawns the server as a subprocess), HTTP requires a pre-running server.
- **Using `url` instead of `httpUrl` in Gemini CLI:** `url` is for SSE transport (deprecated). `httpUrl` is for Streamable HTTP.
- **Using `httpUrl` instead of `serverUrl` in Antigravity:** Antigravity uses a different key. Wrong key = server won't connect.
- **Leaving both stdio and HTTP configs active in Gemini CLI:** May cause tool name conflicts. When testing HTTP, consider disabling the stdio server: `gemini mcp disable form-filler`.
- **Skipping the `/mcp` path in the URL:** The endpoint is `http://127.0.0.1:8000/mcp`, not `http://127.0.0.1:8000`. Missing `/mcp` will return 404.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP client protocol | Custom HTTP client to test server | Gemini CLI / Antigravity native MCP support | Real-world validation with actual MCP clients, not synthetic tests. Phase 3 already has synthetic HTTP tests. |
| Documentation templates | Custom doc generator | Simple markdown files in `docs/` | Plain markdown is readable, version-controllable, and doesn't need a build step. |
| Pipeline orchestration scripts | Automated end-to-end test script | Manual agent-driven pipeline via prompts | The point is to verify that real AI agents can discover and use the tools. Scripts would bypass the agent entirely. |

**Key insight:** Phase 4 is verification, not implementation. The code is done. The work is manual testing with real platforms and documenting what was tested.

## Common Pitfalls

### Pitfall 1: Server Not Running Before Client Connection
**What goes wrong:** Gemini CLI or Antigravity reports "Connection refused" or "Disconnected" for the HTTP MCP server.
**Why it happens:** HTTP transport requires a pre-running server. Unlike stdio (where the client spawns the server process), HTTP clients connect to an already-running endpoint.
**How to avoid:** Always start `python -m src.server --transport http` in a separate terminal BEFORE opening Gemini CLI or Antigravity. Verify the server is up by checking uvicorn's "Uvicorn running on http://127.0.0.1:8000" output.
**Warning signs:** `Disconnected` status in `gemini mcp list` or `Connection refused` errors in Antigravity.

### Pitfall 2: Wrong URL Key in Antigravity Config
**What goes wrong:** Antigravity doesn't connect to the server even though the URL is correct.
**Why it happens:** Antigravity uses `serverUrl` while Gemini CLI uses `httpUrl`. Using the wrong key silently fails.
**How to avoid:** Always use `serverUrl` in `~/.gemini/antigravity/mcp_config.json` and `httpUrl` in `~/.gemini/settings.json`.
**Warning signs:** Server appears in config but shows no tools or stays disconnected.

### Pitfall 3: Tool Name Conflicts Between Stdio and HTTP Servers
**What goes wrong:** Tools from the same server registered under both stdio and HTTP get prefixed with server names (e.g., `form_filler__extract_structure_compact` and `form_filler_http__extract_structure_compact`).
**Why it happens:** Gemini CLI resolves duplicate tool names by prefixing with server name.
**How to avoid:** When testing HTTP, disable the stdio server: `gemini mcp disable form-filler`. Or only configure one transport at a time.
**Warning signs:** Tool calls fail because the agent uses the unprefixed name while the actual registered name has a prefix.

### Pitfall 4: Gemini CLI Auth Error in Non-Interactive Shell
**What goes wrong:** Running `gemini mcp list` from a script or non-interactive terminal fails with `FatalAuthenticationError: Interactive consent could not be obtained`.
**Why it happens:** Gemini CLI requires OAuth authentication via browser. Non-interactive shells can't complete the OAuth flow.
**How to avoid:** Run Gemini CLI from an interactive terminal. If needed, use `NO_BROWSER=true` for manual authentication. The auth token is cached in `~/.gemini/` after first successful login.
**Warning signs:** Error mentioning `FatalAuthenticationError` and `Interactive consent could not be obtained`.

### Pitfall 5: Missing /mcp Path in URL
**What goes wrong:** Client connects but gets 404 errors on every request.
**Why it happens:** The MCP endpoint is at `/mcp`, not at the root `/`. FastMCP's `streamable_http_app()` routes all MCP traffic through `/mcp`.
**How to avoid:** Always include `/mcp` in the URL: `http://127.0.0.1:8000/mcp`.
**Warning signs:** 404 errors in server logs, "Not Found" errors in client.

### Pitfall 6: Antigravity Stalling on Tool Calls
**What goes wrong:** Antigravity connects but tool calls hang indefinitely.
**Why it happens:** Known issue reported in FastMCP issue #2489 -- Antigravity may have problems with certain MCP server configurations, particularly around session handling.
**How to avoid:** If stalling occurs, try restarting Antigravity. If persistent, check whether the issue is specific to streaming responses. The server uses `timeout_graceful_shutdown=5` which should prevent indefinite hangs on the server side.
**Warning signs:** Tool call spinner never resolves, no activity in server logs after initial connection.

## Code Examples

No new code is needed for Phase 4. The examples below are configuration snippets and verification commands.

### Starting the HTTP Server
```bash
# From the project root:
cd /home/sarturko/vibe-legal-form-filler
python -m src.server --transport http
# Expected output:
# INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Gemini CLI: Add HTTP Server
```bash
# Option A: CLI command (writes to settings.json automatically)
gemini mcp add --transport http --trust form-filler-http http://127.0.0.1:8000/mcp

# Option B: Manual settings.json edit
# Edit ~/.gemini/settings.json and add:
# "form-filler-http": { "httpUrl": "http://127.0.0.1:8000/mcp", "trust": true }
```

### Gemini CLI: Verify Tool Discovery
```bash
# Inside a Gemini CLI session:
/mcp
# Expected: form-filler-http shows CONNECTED with 7 tools listed
```

### Gemini CLI: List Tools
```bash
# Non-interactive check (may need auth):
gemini mcp list
# Expected: form-filler-http: http://127.0.0.1:8000/mcp (http) - Connected
```

### Antigravity: Configure HTTP Server
```json
// ~/.gemini/antigravity/mcp_config.json
{
  "mcpServers": {
    "form-filler-http": {
      "serverUrl": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### Antigravity: Verify Tool Discovery
```
1. Open Antigravity
2. Click "..." (three-dot menu) in the Agent panel
3. Select "MCP Servers"
4. form-filler-http should appear with tools listed
5. Click "Manage MCP Servers" to see details
```

### Pipeline Test Prompt (for both platforms)
```
Using the form-filler MCP tools, fill out the questionnaire at
tests/fixtures/table_questionnaire.docx:

1. extract_structure_compact(file_path="tests/fixtures/table_questionnaire.docx")
2. Identify 2-3 answer targets from the compact_text
3. validate_locations for those element IDs
4. build_insertion_xml for each answer
5. write_answers with output_file_path="/tmp/filled_questionnaire.docx"
6. verify_output on the filled document

Report each step's result.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSE transport (`url` key in Gemini CLI) | Streamable HTTP (`httpUrl` key) | Gemini CLI ~0.1.16 (mid-2025) | `url` is for legacy SSE; `httpUrl` is for Streamable HTTP. Always use `httpUrl`. |
| Antigravity `url` key | Antigravity `serverUrl` key | Antigravity ~1.0 (late 2025) | Antigravity uses its own key name, different from Gemini CLI. |
| MCP SDK SSE-only transport | Streamable HTTP as primary transport | MCP SDK ~1.8.0 (March 2025) | Streamable HTTP is the standard; SSE is deprecated but still supported. |

**Deprecated/outdated:**
- SSE transport: Deprecated since August 2025 per MCP spec. Both Gemini CLI and Antigravity support it but Streamable HTTP is preferred.
- `url` key in Gemini CLI settings: Used for SSE endpoints only. Use `httpUrl` for Streamable HTTP.

## Open Questions

1. **Antigravity HTTP transport reliability**
   - What we know: There is a known issue (FastMCP #2489) where Antigravity stalls on tool calls with remote/HTTP MCP servers. The issue was closed as duplicate with no public resolution.
   - What's unclear: Whether this affects our FastMCP server specifically, or if it was fixed in Antigravity 1.15.8.
   - Recommendation: Attempt the connection. If it stalls, document the issue and note it as a known limitation. If it works, document the working config. Either outcome is valid for the verification phase.
   - Confidence: MEDIUM -- the issue may or may not be resolved.

2. **Antigravity `serverUrl` vs `httpUrl` vs `url`**
   - What we know: Official Google docs (developers.google.com/knowledge/mcp) show Antigravity using `serverUrl` while Gemini CLI uses `httpUrl`. GitHub MCP server install guide also uses `serverUrl` for Antigravity.
   - What's unclear: Whether Antigravity also accepts `httpUrl` as an alias.
   - Recommendation: Use `serverUrl` as documented. If it fails, try `httpUrl` as a fallback. Document whichever works.
   - Confidence: HIGH for `serverUrl` being correct.

3. **Tool count discrepancy: 7 vs "all 6 tools plus utilities"**
   - What we know: The server registers 7 tools: `extract_structure_compact`, `extract_structure`, `validate_locations`, `build_insertion_xml`, `write_answers`, `verify_output`, `list_form_fields`. The requirements say "6 tools plus utilities."
   - What's unclear: Whether `list_form_fields` counts as the 7th "tool" or a "utility" alongside the unimplemented `extract_text`.
   - Recommendation: Verify all 7 registered tools are discoverable. The success criteria says "all 6 tools plus utilities" -- `list_form_fields` is one such utility. Count should be 7 total.
   - Confidence: HIGH -- just verify the count matches.

4. **Documentation location: `docs/` or README sections**
   - What we know: The `docs/` directory exists but is empty. `CLAUDE.md` has extensive docs but those are for agents, not for setup guides.
   - What's unclear: Whether to put platform setup guides in `docs/` as separate files or in a single file.
   - Recommendation: Create individual files in `docs/` for each guide. Easier to maintain, link to, and read independently.
   - Confidence: HIGH -- standard practice.

## Sources

### Primary (HIGH confidence)
- Gemini CLI v0.28.2 installed on this machine -- `gemini --version`, `gemini mcp add --help`, `gemini mcp list` all verified
- Gemini CLI settings at `~/.gemini/settings.json` -- inspected directly, shows existing stdio form-filler config
- Antigravity v1.15.8 installed on this machine -- `dpkg -l | grep antigravity` verified
- Antigravity config directory at `~/.gemini/antigravity/` -- verified exists with `mcp_config.json`
- MCP server endpoint at `/mcp` -- verified by inspecting `mcp.streamable_http_app()` routes
- [Gemini CLI official MCP docs](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html) -- `httpUrl` for HTTP, `url` for SSE
- [GitHub MCP Server Antigravity install guide](https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-antigravity.md) -- `serverUrl` for HTTP, config at `~/.gemini/antigravity/mcp_config.json`
- [Google Developer Knowledge MCP setup](https://developers.google.com/knowledge/mcp) -- shows both Gemini CLI (`httpUrl`) and Antigravity (`serverUrl`) configs side by side
- Server tool registration verified: 7 tools registered (inspected via Python)
- 234 tests passing verified: `pytest tests/ -x -q` run

### Secondary (MEDIUM confidence)
- [n8n-mcp Antigravity setup guide](https://github.com/czlonkowski/n8n-mcp/blob/main/docs/ANTIGRAVITY_SETUP.md) -- step-by-step Antigravity config process, verified against official paths
- [Gemini CLI on ChromeOS guide](https://medium.com/gemini-cli-for-the-masses/chromeos-with-gemini-cli-f37079f532d4) -- ChromeOS-specific setup details
- [FastMCP + Gemini CLI integration](https://gofastmcp.com/integrations/gemini-cli) -- confirms stdio works, defers to native config for HTTP
- [Gemini CLI GitHub issue #5268](https://github.com/google-gemini/gemini-cli/issues/5268) -- Streamable HTTP connection issue, resolved in v0.1.16+

### Tertiary (LOW confidence)
- [FastMCP issue #2489](https://github.com/jlowin/fastmcp/issues/2489) -- Antigravity stalling on remote MCP, closed as duplicate with no public resolution. May or may not affect this server.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Both platforms verified installed on this machine with correct versions. Config file locations and formats verified against multiple official sources.
- Architecture: HIGH -- No new architecture needed. This is configuration + manual testing + documentation. Server endpoint, tool count, and test fixtures all verified locally.
- Pitfalls: HIGH -- Most pitfalls discovered through direct observation (auth error from non-interactive shell, settings.json inspection, Antigravity key naming difference confirmed via official docs). The Antigravity stalling issue is MEDIUM confidence (reported but may be resolved).

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (Gemini CLI and Antigravity update frequently, but MCP config format is stable)
