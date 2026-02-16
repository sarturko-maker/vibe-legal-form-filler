# Phase 1: Transport Setup - Research

**Researched:** 2026-02-16
**Domain:** MCP transport layer (stdio + streamable-http), CLI argument parsing, HTTP server lifecycle
**Confidence:** HIGH

## Summary

FastMCP (via `mcp==1.25.0` installed, `1.26.0` declared in pyproject.toml) already supports `streamable-http` transport natively. The `FastMCP.run(transport='streamable-http')` method creates a Starlette ASGI app, wraps it in uvicorn, and serves on `self.settings.host:self.settings.port`. All 6 MCP tools registered via `@mcp.tool()` decorators are automatically available on both transports -- no re-registration needed.

The implementation path is straightforward: add argparse CLI parsing to `server.py`, modify `mcp.settings.host`/`mcp.settings.port` based on CLI flags, then dispatch to either `mcp.run()` (stdio) or a custom HTTP runner that adds port conflict detection and graceful shutdown timeout. The custom runner calls `mcp.streamable_http_app()` to get the Starlette app, then creates its own `uvicorn.Config` with `timeout_graceful_shutdown`. This avoids monkey-patching or subclassing FastMCP.

All required dependencies (uvicorn, starlette, sse-starlette) are already in `requirements.txt` as transitive dependencies of `mcp`. No new packages needed.

**Primary recommendation:** Use `mcp.streamable_http_app()` + custom uvicorn runner in `src/http_transport.py` for the HTTP path. Keep `mcp.run()` for stdio. Add argparse to `server.py` with `--transport`, `--port`, `--host` flags. Add `console_scripts` entry point to `pyproject.toml`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use `--transport {stdio,http}` (choices) instead of a boolean `--http` flag -- more extensible
- Default is `stdio` -- shown explicitly in `--help` output
- Add `--port` flag (default 8000) for HTTP transport
- Add `--host` flag (default 127.0.0.1) for HTTP transport
- `--port` and `--host` error and exit if used without `--transport http` -- no silent ignore
- argparse handles both `--transport=http` and `--transport http` (native behavior)
- `--help` includes usage examples in epilog (e.g., `mcp-form-filler --transport http --port 9000`)
- Port validated to range 1024-65535 -- reject privileged and invalid ports with clear error
- Environment variable fallbacks: `MCP_FORM_FILLER_TRANSPORT`, `MCP_FORM_FILLER_PORT`, `MCP_FORM_FILLER_HOST` -- CLI flags take precedence
- Use argparse (stdlib) -- no additional CLI dependencies
- Both `python -m src.server` and named script `mcp-form-filler` work
- Add `console_scripts` entry in pyproject.toml for `mcp-form-filler`
- server.py remains the entry point -- CLI parsing and transport dispatch stay there
- If port is in use: print `Error: Port 8000 is already in use. Try: --port 8001` and exit non-zero
- No auto-increment, no process info lookup -- simple clear message with suggestion
- Graceful shutdown on Ctrl+C -- finish in-flight requests (with timeout), then exit cleanly
- HTTP transport logic in a single file: `src/http_transport.py`
- Strict 200-line file limit applies -- split if it exceeds
- Use FastMCP's built-in streamable HTTP support (`mcp.run(transport='streamable-http')`) -- minimal custom code
- server.py handles CLI parsing and dispatches to either stdio or HTTP startup path

### Claude's Discretion
- Exact argparse group/subcommand structure
- Graceful shutdown timeout duration
- How FastMCP's built-in HTTP is configured (if it needs ASGI middleware, etc.)
- Error message formatting details

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRANS-01 | Server accepts `--transport http` flag to start in Streamable HTTP mode (default remains stdio) | FastMCP.run() accepts `transport='streamable-http'` natively. Argparse `--transport {stdio,http}` maps `http` -> `streamable-http` for the FastMCP call. Verified: `mcp.run(transport='streamable-http')` creates uvicorn server on configured host:port. |
| TRANS-02 | HTTP mode binds to localhost (127.0.0.1) only | FastMCP defaults to `host='127.0.0.1'`. Auto-enables DNS rebinding protection for localhost (verified: `TransportSecuritySettings` with `allowed_hosts=['127.0.0.1:*', 'localhost:*', '[::1]:*']`). No changes needed for default behavior. `--host` flag allows override. |
| TRANS-07 | Stdio transport continues working exactly as before (no behavioral changes) | Current code: `mcp.run()` defaults to stdio. New code: `mcp.run()` still called for stdio path. No changes to tool registration, mcp_app.py, or tool modules. 207 existing tests validate stdio behavior. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp (FastMCP) | 1.25.0 (installed) / 1.26.0 (declared) | MCP server framework with built-in streamable-http transport | Official MCP Python SDK. `mcp.run(transport='streamable-http')` handles all protocol details. |
| uvicorn | 0.40.0 | ASGI server for HTTP transport | Already a dependency of `mcp`. Supports `timeout_graceful_shutdown`, signal handling (SIGINT/SIGTERM). |
| starlette | 0.52.1 | ASGI framework (used internally by FastMCP) | Already a dependency of `mcp`. `mcp.streamable_http_app()` returns a `Starlette` instance. |
| argparse | stdlib | CLI argument parsing | User decision: stdlib only, no additional CLI dependencies. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| socket | stdlib | Port availability pre-check | Before starting uvicorn, check if port is already bound. |
| errno | stdlib | Error code constants (EADDRINUSE) | Distinguish "port in use" from other socket errors. |
| signal | stdlib | Graceful shutdown (if custom handling needed beyond uvicorn) | Uvicorn handles SIGINT/SIGTERM natively; may not need direct use. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom uvicorn runner | `mcp.run(transport='streamable-http')` directly | Simpler but no port conflict detection, no custom graceful shutdown timeout. User requires both. |
| argparse | click | Click is more powerful but user locked in argparse (stdlib, no deps). |

**Installation:**
No new packages needed. All dependencies already in `requirements.txt`.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── server.py           # Entry point: CLI parsing + transport dispatch (modified)
├── mcp_app.py          # FastMCP instance (unchanged)
├── http_transport.py   # NEW: HTTP startup (port check, uvicorn runner, graceful shutdown)
├── __main__.py         # NEW: enables `python -m src` invocation
├── tools_extract.py    # Tool modules (unchanged)
├── tools_write.py      # Tool modules (unchanged)
└── ...                 # Everything else unchanged
```

### Pattern 1: Settings Modification Before Run
**What:** `mcp_app.py` creates `mcp = FastMCP("form-filler")` with defaults. `server.py` modifies `mcp.settings.host` and `mcp.settings.port` after import but before calling run/dispatch.
**When to use:** Always, for HTTP transport.
**Why it works:** Verified that `mcp.settings` is mutable after construction. Tool registration via `@mcp.tool()` happens at import time and is independent of settings. Settings are only read when `run()` or `streamable_http_app()` is called.
```python
# In server.py, after parsing args:
from src.mcp_app import mcp

if args.transport == "http":
    mcp.settings.host = args.host or "127.0.0.1"
    mcp.settings.port = args.port or 8000
    # Then dispatch to HTTP runner
```
**Verified:** Settings modification after tool registration works correctly (tested in Python REPL).

### Pattern 2: Custom HTTP Runner (port check + graceful shutdown)
**What:** Instead of calling `mcp.run(transport='streamable-http')`, get the Starlette app via `mcp.streamable_http_app()` and run uvicorn with custom config.
**When to use:** HTTP transport only. Enables port conflict detection and configurable graceful shutdown timeout.
**Why not just use mcp.run():** `mcp.run(transport='streamable-http')` calls `run_streamable_http_async()` which creates uvicorn config WITHOUT `timeout_graceful_shutdown` and WITHOUT port pre-checking. We need both.
```python
# In http_transport.py:
import anyio
import socket
import errno
import sys
import uvicorn
from src.mcp_app import mcp

GRACEFUL_SHUTDOWN_TIMEOUT = 5  # seconds

def check_port_available(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            return False
        raise
    finally:
        sock.close()

async def run_http(host: str, port: int) -> None:
    starlette_app = mcp.streamable_http_app()
    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level=mcp.settings.log_level.lower(),
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT,
    )
    server = uvicorn.Server(config)
    await server.serve()

def start_http(host: str, port: int) -> None:
    if not check_port_available(host, port):
        print(f"Error: Port {port} is already in use. Try: --port {port + 1}", file=sys.stderr)
        sys.exit(1)
    anyio.run(run_http, host, port)
```
**Verified:** `mcp.streamable_http_app()` returns a `Starlette` instance that works with custom `uvicorn.Config`. `timeout_graceful_shutdown` is supported by uvicorn 0.40.0.

### Pattern 3: Environment Variable Fallbacks with CLI Override
**What:** argparse defaults read from env vars, but CLI flags take precedence.
**When to use:** For all three flags (`--transport`, `--port`, `--host`).
```python
import os

parser.add_argument(
    '--transport',
    choices=['stdio', 'http'],
    default=os.environ.get('MCP_FORM_FILLER_TRANSPORT', 'stdio'),
    help='Transport protocol (default: stdio). Env: MCP_FORM_FILLER_TRANSPORT',
)
parser.add_argument(
    '--port',
    type=validate_port,
    default=None,  # Resolved later with env fallback
    help='Port for HTTP transport (default: 8000). Env: MCP_FORM_FILLER_PORT',
)
```
**Note:** `--port` and `--host` use `default=None` so we can detect whether they were explicitly provided. Env var fallback applied in validation step, not in argparse default, to properly enforce the "error if used without --transport http" rule.

### Pattern 4: console_scripts Entry Point
**What:** Add `[project.scripts]` to `pyproject.toml` for the `mcp-form-filler` command.
**When to use:** After implementation, requires `pip install -e .` to activate.
```toml
[project.scripts]
mcp-form-filler = "src.server:main"
```
**Requires:** Refactoring `server.py` to have a `main()` function instead of bare `if __name__ == "__main__"` block.

### Anti-Patterns to Avoid
- **Modifying mcp_app.py:** Tool modules import `mcp` from `mcp_app.py` at import time. Don't add transport logic there -- it must stay a simple singleton.
- **Passing host/port to FastMCP constructor:** Would require moving the FastMCP instantiation into `server.py` after arg parsing, breaking the existing import chain.
- **Using FASTMCP_ env vars:** FastMCP's `Settings` class reads `FASTMCP_PORT` etc., but `FastMCP.__init__` passes explicit defaults that override env vars. These effectively don't work. Use our own `MCP_FORM_FILLER_*` prefix.
- **Subclassing FastMCP:** Unnecessary complexity. Settings modification + custom runner achieves everything needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP/MCP protocol handling | Custom HTTP handler | `mcp.streamable_http_app()` | Returns fully-configured Starlette app with MCP session management, DNS rebinding protection, correct routing. |
| ASGI server | Custom event loop + socket server | `uvicorn.Server` + `uvicorn.Config` | Handles signal capture, graceful shutdown, connection draining, HTTP/1.1 keep-alive. |
| MCP session management | Custom session tracking | `StreamableHTTPSessionManager` (internal to FastMCP) | Manages client sessions, event stores, retries. Created by `streamable_http_app()`. |
| DNS rebinding protection | Custom Host header validation | FastMCP auto-enables for localhost | `TransportSecuritySettings` with correct allowed_hosts/origins created automatically when `host='127.0.0.1'`. |

**Key insight:** The MCP SDK's FastMCP class does 95% of the work. Our `http_transport.py` is a thin wrapper that adds port pre-checking and graceful shutdown timeout -- about 50-80 lines total.

## Common Pitfalls

### Pitfall 1: Port Conflict Race Condition
**What goes wrong:** Port is free when checked but taken by the time uvicorn binds.
**Why it happens:** Another process binds the port between our `check_port_available()` call and uvicorn's `bind()`.
**How to avoid:** Accept the race as an inherent TOCTOU issue. Uvicorn will raise its own error if this happens. The pre-check is a UX improvement for the common case, not a guarantee.
**Warning signs:** None needed -- this is extremely rare in development scenarios.

### Pitfall 2: `__main__.py` vs `server.py` __main__ block
**What goes wrong:** `python -m src` (package) and `python -m src.server` (module) are different invocations.
**Why it happens:** `python -m src` looks for `src/__main__.py`. `python -m src.server` runs `src/server.py` with `__name__ == '__main__'`.
**How to avoid:** Create both: (1) `src/__main__.py` that imports and calls `main()` from `server.py`, and (2) keep the `if __name__ == "__main__": main()` in `server.py`.
**Warning signs:** `python -m src.server` works but `python -m src` gives "No module named src.__main__".

### Pitfall 3: Tool Registration Timing
**What goes wrong:** Tools not available in HTTP mode because they weren't imported before `streamable_http_app()` is called.
**Why it happens:** Tool registration happens via `@mcp.tool()` decorators at import time. If `tools_extract.py` and `tools_write.py` aren't imported, tools aren't registered.
**How to avoid:** Keep the existing import chain in `server.py`. The imports of `tools_extract` and `tools_write` happen at module level, before any transport dispatch code runs. Verify with a test that lists available tools after HTTP startup.
**Warning signs:** HTTP endpoint returns empty tool list while stdio works fine.

### Pitfall 4: Env Var Validation for --port and --host
**What goes wrong:** User sets `MCP_FORM_FILLER_PORT=9000` without `MCP_FORM_FILLER_TRANSPORT=http`, and the port value is silently accepted but ignored.
**Why it happens:** If env vars feed directly into argparse defaults, the "error if used without --transport http" validation might not catch env-sourced values.
**How to avoid:** Don't use env vars as argparse defaults for `--port` and `--host`. Instead, resolve env vars in a post-parse validation step that also checks for the misuse condition.
**Warning signs:** Test with `MCP_FORM_FILLER_PORT=9000 python -m src.server` (no --transport http) -- should error.

### Pitfall 5: FastMCP DNS Rebinding Protection with Non-localhost Host
**What goes wrong:** If user passes `--host 0.0.0.0`, FastMCP's auto DNS rebinding protection is NOT enabled (it only triggers for `127.0.0.1`, `localhost`, `::1`).
**Why it happens:** The auto-detection in `FastMCP.__init__` only checks for localhost variants.
**How to avoid:** For this phase, document that `--host` defaults to `127.0.0.1` and non-localhost hosts bypass DNS rebinding protection. This is acceptable for personal Chromebook use.
**Warning signs:** None for personal use. Would matter for network-exposed deployments.

## Code Examples

Verified patterns from official sources and REPL testing:

### CLI Argument Parsing (server.py main function)
```python
# Verified: argparse handles both --transport=http and --transport http natively
import argparse
import os
import sys

def validate_port(value: str) -> int:
    """Validate port is in allowed range 1024-65535."""
    port = int(value)
    if port < 1024 or port > 65535:
        raise argparse.ArgumentTypeError(
            f"Port must be between 1024 and 65535, got {port}"
        )
    return port

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-form-filler",
        description="MCP server exposing form-filling tools for copilot agents",
        epilog=(
            "Examples:\n"
            "  mcp-form-filler                              # stdio (default)\n"
            "  mcp-form-filler --transport http              # HTTP on 127.0.0.1:8000\n"
            "  mcp-form-filler --transport http --port 9000  # HTTP on custom port\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("MCP_FORM_FILLER_TRANSPORT", "stdio"),
        help="Transport protocol (default: stdio). Env: MCP_FORM_FILLER_TRANSPORT",
    )
    parser.add_argument(
        "--port",
        type=validate_port,
        default=None,
        help="Port for HTTP transport (default: 8000). Env: MCP_FORM_FILLER_PORT",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host for HTTP transport (default: 127.0.0.1). Env: MCP_FORM_FILLER_HOST",
    )
    return parser
```

### Port Conflict Detection (http_transport.py)
```python
# Verified: socket.bind() raises OSError(errno.EADDRINUSE) when port in use
import socket
import errno
import sys

def check_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding. Returns True if available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            return False
        raise
    finally:
        sock.close()
```

### Custom HTTP Runner with Graceful Shutdown (http_transport.py)
```python
# Verified: mcp.streamable_http_app() returns Starlette, works with custom uvicorn.Config
import anyio
import uvicorn
from src.mcp_app import mcp

GRACEFUL_SHUTDOWN_TIMEOUT = 5  # seconds

async def _run_http_async(host: str, port: int) -> None:
    """Start uvicorn with the FastMCP Starlette app."""
    starlette_app = mcp.streamable_http_app()
    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level=mcp.settings.log_level.lower(),
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT,
    )
    server = uvicorn.Server(config)
    await server.serve()

def start_http(host: str, port: int) -> None:
    """Check port availability, then start the HTTP server."""
    if not check_port_available(host, port):
        print(
            f"Error: Port {port} is already in use. Try: --port {port + 1}",
            file=sys.stderr,
        )
        sys.exit(1)
    anyio.run(_run_http_async, host, port)
```

### console_scripts Entry Point (pyproject.toml)
```toml
[project.scripts]
mcp-form-filler = "src.server:main"
```

### __main__.py (enables python -m src)
```python
"""Allow running as `python -m src`."""
from src.server import main

main()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSE transport (`mcp.run(transport='sse')`) | Streamable HTTP (`mcp.run(transport='streamable-http')`) | MCP SDK ~1.8.0 (March 2025) | Single endpoint, bidirectional, replaces SSE as recommended HTTP transport |
| Custom HTTP wrapper process | Built-in `FastMCP.run(transport='streamable-http')` | Same timeframe | No need for separate HTTP layer; FastMCP handles everything |
| `FASTMCP_` env vars for config | These exist but are overridden by FastMCP constructor defaults | Current behavior | Don't rely on `FASTMCP_PORT` etc. -- use custom env var prefix |

**Deprecated/outdated:**
- SSE transport: Still supported but superseded by streamable-http. Don't use for new work.
- `mcp.run(transport='sse')`: Works but streamable-http is the current standard.

## Open Questions

1. **Graceful shutdown timeout duration**
   - What we know: Uvicorn supports `timeout_graceful_shutdown` (integer seconds). Default is `None` (wait indefinitely).
   - What's unclear: What's a reasonable timeout for MCP form-filling operations (which can involve large document processing)?
   - Recommendation: Use 5 seconds. Form-filling operations are typically sub-second (XML manipulation, not LLM calls). 5 seconds is generous. Configurable via constant in `http_transport.py`.

2. **Argparse group structure**
   - What we know: Need `--transport`, `--port`, `--host` flags with cross-validation.
   - Options: (a) Flat args with post-parse validation, (b) Mutually exclusive group, (c) Argument groups for display.
   - Recommendation: Flat args with `argparse.ArgumentParser` (no groups). Post-parse validation rejects `--port`/`--host` without `--transport http`. Simpler code, cleaner `--help` output. Argument groups add visual complexity without value for 3 flags.

3. **Whether `mcp.settings.host`/`port` need modification or just pass to custom runner**
   - What we know: Custom runner takes host/port as params. But `mcp.streamable_http_app()` also reads `mcp.settings.host`/`port` internally (for DNS rebinding protection configuration).
   - Recommendation: Modify `mcp.settings.host` and `mcp.settings.port` BEFORE calling `mcp.streamable_http_app()` so DNS rebinding protection is configured correctly for the actual host. Then also pass host/port explicitly to the uvicorn config.

## Sources

### Primary (HIGH confidence)
- FastMCP source code (installed `mcp==1.25.0`) - `FastMCP.run()`, `FastMCP.__init__()`, `FastMCP.run_streamable_http_async()`, `FastMCP.streamable_http_app()`, `Settings` class -- all inspected via `inspect.getsource()` in Python REPL
- Uvicorn source code (installed `uvicorn==0.40.0`) - `Config.__init__`, `Server.serve`, `Server.capture_signals` -- inspected via REPL
- Project source code -- `server.py`, `mcp_app.py`, `pyproject.toml`, `requirements.txt`, all test files

### Secondary (MEDIUM confidence)
- [FastMCP Running Server docs](https://gofastmcp.com/deployment/running-server) - Confirmed `mcp.run(transport="http")` pattern and CLI usage
- [Python Packaging User Guide - pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - `[project.scripts]` format for console_scripts
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) - Streamable HTTP transport overview

### Tertiary (LOW confidence)
- None. All findings verified via REPL or official source inspection.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and verified via REPL. FastMCP's streamable-http support confirmed by reading actual source code.
- Architecture: HIGH - Settings modification pattern, custom runner, port checking all verified in Python REPL. No speculative claims.
- Pitfalls: HIGH - Each pitfall discovered through direct testing (e.g., FASTMCP_ env vars don't work, DNS rebinding only for localhost, __main__.py vs __main__ block distinction).

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (stable -- MCP SDK is mature, uvicorn is stable, argparse is stdlib)
