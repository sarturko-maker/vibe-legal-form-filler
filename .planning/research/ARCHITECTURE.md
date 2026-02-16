# Architecture Research: Dual-Transport MCP Servers

**Domain:** MCP server with stdio and HTTP transport
**Researched:** 2026-02-16
**Confidence:** HIGH

## Standard Architecture

### System Overview

The Model Context Protocol ecosystem uses a **transport-agnostic core with swappable transport layers**. The same MCP server logic can be exposed via different transports selected at runtime, without changing the business logic.

```
┌─────────────────────────────────────────────────────────────┐
│                   Transport Selection Layer                  │
│  (Runtime decision: CLI flag, env var, or __main__ logic)   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┐              ┌──────────────┐            │
│   │ STDIO        │              │ HTTP         │            │
│   │ Transport    │              │ Transport    │            │
│   │              │              │ (Streamable) │            │
│   └──────┬───────┘              └──────┬───────┘            │
│          │                             │                    │
├──────────┴─────────────────────────────┴────────────────────┤
│                   FastMCP Server Core                        │
│              (mcp = FastMCP("server-name"))                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  Tool   │  │  Tool   │  │  Tool   │  │  Tool   │        │
│  │ Module  │  │ Module  │  │ Module  │  │ Module  │        │
│  │    1    │  │    2    │  │    3    │  │    4    │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
├───────┴────────────┴────────────┴────────────┴──────────────┤
│                    Business Logic Layer                      │
│            (handlers, validators, xml_utils, models)         │
├─────────────────────────────────────────────────────────────┤
│                       External I/O                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │   File   │  │  OOXML   │  │  Excel   │                   │
│  │  System  │  │  Parser  │  │  Parser  │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Transport Layer** | Message serialization/deserialization, connection management, protocol compliance | FastMCP's built-in stdio/HTTP transports — no custom code needed |
| **FastMCP Core** | Tool registration, routing, JSON-RPC handling | `mcp = FastMCP("name")` singleton, `@mcp.tool()` decorators |
| **Tool Modules** | MCP tool definitions (inputs, outputs, business logic delegation) | Separate Python files per domain, each imports `mcp` and uses decorators |
| **Business Logic** | Domain-specific work (parsing, validation, manipulation, output generation) | Pure Python functions/classes with no MCP dependencies |
| **External I/O** | File reading/writing, XML/Excel/PDF parsing, third-party library interaction | lxml, python-docx, openpyxl, PyMuPDF |

## Recommended Project Structure

```
src/
├── server.py              # Entry point — thin orchestration layer
│                           # Imports tool modules (triggers registration)
│                           # Calls mcp.run() with transport from CLI/env
├── mcp_app.py             # FastMCP singleton instance
│                           # mcp = FastMCP("server-name")
├── tools_extract.py       # Tool module 1: extraction-related @mcp.tool()
├── tools_write.py         # Tool module 2: write-related @mcp.tool()
├── handlers/              # Business logic (transport-agnostic)
│   ├── word.py            # Public API for Word operations
│   ├── word_parser.py     # OOXML parsing logic
│   ├── word_writer.py     # Answer insertion logic
│   ├── excel.py           # Public API for Excel operations
│   └── pdf.py             # Public API for PDF operations
├── xml_utils.py           # XML manipulation helpers
├── validators.py          # Input validation helpers
└── models.py              # Pydantic models (shared types)
```

### Structure Rationale

- **server.py:** Single entry point for all transports. Import-time registration keeps tool modules decoupled from server lifecycle.
- **mcp_app.py:** Separate module avoids circular imports. Tool modules can import `mcp` without importing `server.py`.
- **tools_*.py:** One file per functional domain. Keeps files under 200 lines (vibe coding constraint). Tools delegate to handlers — no business logic in tool functions.
- **handlers/:** Pure Python, no MCP dependencies. Can be tested independently, reused in non-MCP contexts.
- **models.py:** Single source of truth for Pydantic schemas used by tools and handlers.

## Architectural Patterns

### Pattern 1: Import-Time Tool Registration

**What:** Tool modules use `@mcp.tool()` decorators at module level. Tools are registered when the module is imported, not when the server runs.

**When to use:** When you want declarative tool definitions with minimal boilerplate. FastMCP's default pattern.

**Trade-offs:**
- ✅ Clean, concise tool definitions
- ✅ No manual registration calls
- ✅ Tools are discovered automatically
- ⚠️ All tool modules must be imported before `mcp.run()`
- ⚠️ Import order matters if tools have dependencies

**Example:**
```python
# mcp_app.py
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("form-filler")

# tools_extract.py
from src.mcp_app import mcp
from src.handlers.word import extract_structure_compact as word_extract

@mcp.tool()
def extract_structure_compact(file_path: str, file_type: str = None):
    """Extract compact indexed structure from a form document."""
    return word_extract(file_path, file_type)

# server.py
from src.mcp_app import mcp
from src.tools_extract import extract_structure_compact  # triggers registration
from src.tools_write import write_answers  # triggers registration

if __name__ == "__main__":
    mcp.run()  # tools already registered
```

### Pattern 2: Runtime Transport Selection

**What:** The same server.py can launch with different transports based on CLI flags or environment variables. No code changes needed to switch transports.

**When to use:** When you need the same server to work locally (stdio) and remotely (HTTP) without maintaining separate entry points.

**Trade-offs:**
- ✅ Single codebase, multiple deployment modes
- ✅ Developer can test locally with stdio, deploy with HTTP
- ✅ No duplicate logic between transport modes
- ⚠️ Requires runtime configuration (CLI args, env vars, or config files)

**Example:**
```python
# server.py (Pattern A: CLI-based selection)
import sys
from src.mcp_app import mcp
from src import tools_extract, tools_write  # trigger registration

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
    else:
        mcp.run()  # defaults to stdio
```

**Alternative using FastMCP CLI:**
```bash
# The FastMCP CLI handles transport selection externally
fastmcp run src/server.py --transport stdio
fastmcp run src/server.py --transport streamable-http --port 8080
```

### Pattern 3: Transport-Agnostic Business Logic

**What:** All domain logic lives in handler modules with no knowledge of MCP or transport mechanisms. Tool functions are thin wrappers that delegate to handlers.

**When to use:** Always. This is the Dependency Inversion Principle applied to MCP servers.

**Trade-offs:**
- ✅ Business logic can be tested without MCP infrastructure
- ✅ Logic can be reused in non-MCP contexts (scripts, other servers)
- ✅ Tools can switch handlers (e.g., different PDF libraries) without changing MCP interface
- ⚠️ Requires discipline to keep tool functions thin (no logic creep)

**Example:**
```python
# handlers/word.py (pure Python, no MCP)
def extract_structure_compact(file_bytes: bytes) -> dict:
    """Extract compact structure. Returns dict with compact_text, id_to_xpath."""
    # ... lxml parsing logic ...
    return {"compact_text": text, "id_to_xpath": mapping}

# tools_extract.py (thin MCP wrapper)
from src.mcp_app import mcp
from src.handlers.word import extract_structure_compact as handler
from src.validators import validate_file_input

@mcp.tool()
def extract_structure_compact(file_path: str = None, file_bytes_b64: str = None):
    """Extract compact indexed structure from a form document."""
    file_bytes, file_type = validate_file_input(file_path, file_bytes_b64)
    result = handler(file_bytes)  # delegate to handler
    return result
```

## Data Flow

### Request Flow (Both Transports)

```
[Client Request]
    ↓
[Transport Layer] → deserializes JSON-RPC message
    ↓
[FastMCP Core] → routes to registered tool by name
    ↓
[Tool Function] → validates inputs (Pydantic)
    ↓
[Validator Helpers] → checks file paths, types, sizes
    ↓
[Handler Function] → performs business logic
    ↓
[External I/O] → reads files, parses XML, writes output
    ↓
[Handler Function] → returns structured data
    ↓
[Tool Function] → returns dict (FastMCP serializes to JSON)
    ↓
[FastMCP Core] → wraps response in JSON-RPC envelope
    ↓
[Transport Layer] → serializes and sends response
    ↓
[Client Response]
```

### STDIO vs HTTP Flow Differences

**STDIO:**
- One process per client session
- Client launches: `python src/server.py`
- Process lifecycle: spawn → initialize → handle requests → exit when client disconnects
- No concurrency within server (single client per process)

**HTTP:**
- One persistent server process, many concurrent clients
- Server launched once: `python src/server.py --http`
- Process lifecycle: spawn → initialize → listen → handle concurrent requests → run indefinitely
- Concurrency managed by uvicorn (FastMCP's underlying ASGI server)
- Stateless tool functions critical (no shared state between requests)

### Key Data Flows

1. **Tool registration flow:** tool module imports → decorator executes → FastMCP.tool() stores tool metadata → mcp.run() builds routing table
2. **STDIO request flow:** stdin JSON → FastMCP deserializes → tool function called → result serialized → stdout JSON
3. **HTTP request flow:** POST /mcp → FastMCP deserializes → tool function called → result serialized → HTTP response
4. **File input flow:** file_path OR file_bytes_b64 → validator → bytes loaded → handler receives raw bytes

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **Single developer (1 user)** | STDIO only. No server infrastructure needed. Claude Desktop or CLI client launches process on demand. |
| **Team (2-50 users)** | Add HTTP transport. Deploy on internal network or localhost. Users connect via HTTP MCP clients. Single server instance adequate. |
| **Organization (50+ users)** | HTTP transport with load balancer. Multiple server instances behind reverse proxy. Consider request queuing for long-running tools. |

### Scaling Priorities

1. **First bottleneck:** Stateful tool functions. If tools share global state, concurrent HTTP requests will conflict. **Fix:** Make all tools stateless and idempotent.
2. **Second bottleneck:** Large file processing in-memory. If tools load 50MB documents into RAM, multiple concurrent requests will exhaust memory. **Fix:** Stream file processing or use temp files with cleanup.
3. **Third bottleneck:** Long-running tools blocking server. If a tool takes 30 seconds to complete, HTTP clients may timeout. **Fix:** Return task ID immediately, provide separate status-check tool.

## Anti-Patterns

### Anti-Pattern 1: Transport-Specific Logic in Tools

**What people do:** Add `if stdio: ... else: ...` branches in tool functions based on transport type.

**Why it's wrong:** Violates transport abstraction. Makes tools untestable without mocking transport layer. Creates maintenance burden when adding new transports.

**Do this instead:** Keep tools transport-agnostic. If behavior must differ, use configuration (env vars, function parameters) not transport detection.

**Example (wrong):**
```python
@mcp.tool()
def extract_structure(file_path: str):
    if is_stdio_transport():
        return full_result  # stdio can handle large responses
    else:
        return truncated_result  # HTTP has size limits
```

**Example (correct):**
```python
@mcp.tool()
def extract_structure_compact(file_path: str):
    """Returns compact representation suitable for any transport."""
    return compact_result

@mcp.tool()
def extract_structure(file_path: str):
    """Returns full representation. Client chooses based on needs."""
    return full_result
```

### Anti-Pattern 2: Inline Tool Registration in server.py

**What people do:** Define tool functions directly in server.py using decorators.

**Why it's wrong:** Violates separation of concerns. server.py becomes a monolith mixing entry point logic with business logic. Hard to maintain under file size constraints (200-line vibe coding limit).

**Do this instead:** Define tools in separate modules, import them in server.py to trigger registration.

**Example (wrong):**
```python
# server.py
from src.mcp_app import mcp

@mcp.tool()
def extract_structure(...):
    # ... 100 lines of logic ...

@mcp.tool()
def write_answers(...):
    # ... 150 lines of logic ...

if __name__ == "__main__":
    mcp.run()
```

**Example (correct):**
```python
# server.py
from src.mcp_app import mcp
from src.tools_extract import extract_structure  # triggers registration
from src.tools_write import write_answers  # triggers registration

if __name__ == "__main__":
    mcp.run()
```

### Anti-Pattern 3: Hardcoded Transport Configuration

**What people do:** Hardcode `mcp.run(transport="streamable-http", port=8080)` in server.py with no CLI override.

**Why it's wrong:** Forces developers to edit code to switch transports. Breaks local development workflows (everyone needs HTTP setup even for testing).

**Do this instead:** Accept transport configuration via CLI flags, environment variables, or default to stdio for development.

**Example (wrong):**
```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8080)  # always HTTP
```

**Example (correct):**
```python
import os
import sys

if __name__ == "__main__":
    if "--http" in sys.argv or os.getenv("MCP_TRANSPORT") == "http":
        port = int(os.getenv("MCP_PORT", "8080"))
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run()  # stdio for local dev
```

### Anti-Pattern 4: Stateful Tool Functions (Critical for HTTP)

**What people do:** Store request state in module-level variables or shared objects.

**Why it's wrong:** Works with stdio (1 process = 1 client) but breaks catastrophically with HTTP (1 process, many concurrent clients). Requests will see each other's state.

**Do this instead:** Keep all tool functions pure and stateless. Accept all inputs as parameters, return all outputs in result. Use function-local variables only.

**Example (wrong):**
```python
# tools_write.py
current_document = None  # shared state!

@mcp.tool()
def load_document(file_path: str):
    global current_document
    current_document = parse_document(file_path)
    return {"status": "loaded"}

@mcp.tool()
def write_answer(answer: str):
    global current_document
    current_document.add_answer(answer)  # uses state from previous request
    return current_document.save()
```

**Example (correct):**
```python
@mcp.tool()
def write_answers(file_path: str, answers: list):
    """Stateless: loads document, writes answers, returns result in one call."""
    document = parse_document(file_path)
    for answer in answers:
        document.add_answer(answer)
    return document.save()
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **FastMCP library** | Import `FastMCP` class, instantiate once, use decorators | Version 2.0+ supports both stdio and streamable-http transports |
| **uvicorn (implicit)** | FastMCP uses uvicorn internally for HTTP transport | No direct integration needed — FastMCP handles this |
| **File system** | Pass file_path to tools, handlers read bytes with open() | Validate paths to prevent directory traversal |
| **lxml, openpyxl, PyMuPDF** | Handlers import and use directly | Transport-agnostic — work identically under stdio and HTTP |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **server.py ↔ tool modules** | Import (triggers registration) | One-way dependency: server imports tools, tools never import server |
| **tool modules ↔ mcp_app** | Import shared FastMCP instance | mcp_app has zero dependencies (avoids circular imports) |
| **tool functions ↔ handlers** | Function calls with Pydantic models | Tools validate inputs, handlers assume valid inputs |
| **handlers ↔ xml_utils/validators** | Function calls | Handlers delegate parsing/validation to specialized utilities |

## Build Order (Adding HTTP to Existing stdio Server)

Given the existing project has:
- ✅ `server.py` imports tool modules, calls `mcp.run()` for stdio
- ✅ `mcp_app.py` holds the shared FastMCP instance
- ✅ Tools registered via `@mcp.tool()` decorators at import time
- ✅ Stateless — no session state
- ✅ 172 passing tests
- ✅ Clean import hierarchy: server.py → tools_* → handlers → xml_utils/validators → models

### Recommended Build Order

**Phase 1: Add Transport Selection (1 file change, ~10 lines)**
1. Modify `server.py` to accept `--http` flag or `MCP_TRANSPORT` env var
2. If flag/env present, call `mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)`
3. Otherwise, call `mcp.run()` (stdio, existing behavior)
4. **No changes to business logic, tool definitions, or handlers**
5. **Test:** Run `python src/server.py` → stdio works (existing tests pass)
6. **Test:** Run `python src/server.py --http` → HTTP server starts

**Phase 2: HTTP Integration Testing (new test file, ~50 lines)**
1. Add `tests/test_http_transport.py`
2. Start server in subprocess with `--http` flag
3. Use HTTP client (httpx or requests) to send JSON-RPC requests
4. Verify responses match stdio behavior
5. Test concurrent requests (ensure stateless tools handle concurrency)
6. **Test:** All existing 172 tests pass with stdio
7. **Test:** New HTTP integration tests pass

**Phase 3: Documentation & Deployment Config (new files, no code changes)**
1. Add `DEPLOYMENT.md` with stdio vs HTTP usage examples
2. Add Docker/systemd service files for HTTP deployment (optional)
3. Update README with transport selection instructions
4. **No code changes** — all changes are documentation and deployment config

**Phase 4: Optional HTTP Enhancements (incremental, non-breaking)**
1. Add health check endpoint for HTTP deployments
2. Add request logging middleware (HTTP only, for monitoring)
3. Add rate limiting (HTTP only, for multi-user scenarios)
4. **All enhancements HTTP-specific** — stdio behavior unchanged

### Key Architectural Decisions

✅ **Do NOT create separate entry points** (`server_stdio.py`, `server_http.py`) — use single entry point with runtime selection

✅ **Do NOT change tool signatures or business logic** — transport is orthogonal to functionality

✅ **Do NOT add FastAPI separately** — FastMCP uses uvicorn internally, no separate ASGI framework needed

✅ **Do NOT create HTTP-specific tool variants** — same tools work with both transports (FastMCP handles serialization)

✅ **Do verify statelessness** — critical for HTTP, benign for stdio, so validate once

### Risk Mitigation

**Risk:** Existing stdio workflows break when HTTP added
**Mitigation:** Make stdio the default (no flags → stdio). HTTP requires explicit flag.

**Risk:** HTTP deployment exposes security issues (path traversal, DOS)
**Mitigation:** Existing validators already check paths. Add rate limiting if deploying publicly.

**Risk:** Tests only cover stdio, HTTP behavior differs
**Mitigation:** Add HTTP integration tests that call the same tools via HTTP and assert identical results.

**Risk:** Concurrent HTTP requests expose hidden state
**Mitigation:** Review all tool functions for global/module state before deploying HTTP. Add concurrency test.

## Sources

### Official Documentation (HIGH confidence)
- [FastMCP Running Your Server](https://gofastmcp.com/deployment/running-server) — transport parameter usage, CLI flags
- [Model Context Protocol Architecture](https://modelcontextprotocol.io/docs/learn/architecture) — official MCP transport abstraction design

### Educational Resources (MEDIUM-HIGH confidence)
- [Dual-Transport MCP Servers: STDIO vs. HTTP Explained](https://medium.com/@kumaran.isk/dual-transport-mcp-servers-stdio-vs-http-explained-bd8865671e1f) — architectural patterns, rationale for dual transport
- [Building and Exposing MCP Servers with FastMCP](https://medium.com/@anil.goyal0057/building-and-exposing-mcp-servers-with-fastmcp-stdio-http-and-sse-ace0f1d996dd) — practical examples of both transports
- [One MCP Server, Two Transports: STDIO and HTTP](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/one-mcp-server-two-transports-stdio-and-http/4443915) — Microsoft's guidance on dual-transport architecture

### Implementation Examples (MEDIUM confidence)
- [fastmcp-transport-guide](https://github.com/tnpaul/fastmcp-transport-guide) — concise guide with Python code examples for stdio, HTTP, SSE
- [simple-mcp-server](https://github.com/rb58853/simple-mcp-server) — Python implementation with FastMCP, FastAPI, and streamable HTTP
- [FastMCP Python SDK](https://github.com/jlowin/fastmcp) — official FastMCP repository with transport implementation

### Recent Updates (MEDIUM confidence)
- [SSE vs Streamable HTTP: Why MCP Switched](https://brightdata.com/blog/ai/sse-vs-streamable-http) — 2026 transport protocol evolution
- [MCP-for-beginners stdio server guide](https://github.com/microsoft/mcp-for-beginners/blob/main/03-GettingStarted/05-stdio-server/README.md) — Microsoft's beginner guide to stdio transport

---
*Architecture research for: Dual-transport MCP server (stdio + HTTP)*
*Researched: 2026-02-16*
*Focus: Adding HTTP transport to existing stdio-only FastMCP server without breaking core logic*
