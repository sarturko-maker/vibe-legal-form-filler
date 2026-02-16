# Phase 3: HTTP Integration Testing - Research

**Researched:** 2026-02-16
**Domain:** MCP HTTP transport integration testing -- transport parity, tool invocation over HTTP, SSE response parsing, concurrent request validation, error handling verification
**Confidence:** HIGH

## Summary

Phase 3 requires integration tests proving that the HTTP transport layer (built in Phases 1-2) works correctly end-to-end. The server already passes 217 unit tests via direct function calls (simulating stdio). The goal now is to verify that the same tools produce identical results when invoked via HTTP (JSON-RPC over Starlette TestClient), that error handling works as specified, and that concurrent requests work on the stateless design.

The core testing pattern is straightforward and has been verified experimentally: Starlette's `TestClient` can invoke MCP tools via JSON-RPC `tools/call` requests, parse SSE responses to extract tool results, and compare those results against direct function calls. Transport parity has been confirmed -- `extract_structure_compact` returns byte-for-byte identical JSON when called directly vs over HTTP. Concurrent requests (via threads + TestClient) work within a single session without interference.

The main structural challenge is the 200-line file limit. Phase 3 tests will need to be split across multiple files: one for transport parity (TEST-02), one for utility testing over HTTP (TEST-03), one for HTTP error responses (TEST-04, extending existing `test_http_protocol.py`), and one for concurrency (TEST-05). Shared fixtures and SSE parsing helpers should live in a `conftest.py` or shared module.

**Primary recommendation:** Use Starlette TestClient with JSON-RPC `tools/call` for all integration tests. Share MCP session setup and SSE response parsing via `conftest.py` fixtures. Split tests across 3-4 files to stay under 200 lines each. Use `threading` for concurrent request tests (no new dependencies needed).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | All 172 existing unit tests pass after transport changes | **217 tests currently passing** (original 172 grew to 207 after Phase 1, then 217 after Phase 2). Verified by running `pytest tests/ -x -q` -- 217 pass. The test suite serves as the regression guard. No new code needed; just run the full suite as a pre-check. |
| TEST-02 | Integration tests confirm all 6 MCP tools produce identical results over stdio and HTTP | **Verified pattern works.** TestClient sends JSON-RPC `tools/call`, response arrives as SSE (`text/event-stream`), tool output is inside `result.content[0].text` as JSON string. Direct function call returns identical dict. Experimentally confirmed with `extract_structure_compact` and `list_form_fields`. Need tests for all 6 core tools: extract_structure_compact, extract_structure, validate_locations, build_insertion_xml, write_answers, verify_output. |
| TEST-03 | Integration tests confirm utilities (extract_text, list_form_fields) work over HTTP | **`list_form_fields` works over HTTP** -- verified via TestClient. **`extract_text` does not exist yet** -- it is described in CLAUDE.md as an optional utility but was never implemented as an MCP tool (no `@mcp.tool()` decorator, no handler module `text_extractor.py`). Tests should cover `list_form_fields` over HTTP and note that `extract_text` is not yet available. |
| TEST-04 | HTTP-specific tests for error responses (406 for wrong Accept, 400 for malformed JSON-RPC, 404 for wrong path) | **Already partially covered** by Phase 2's `test_http_protocol.py` (10 tests covering TRANS-03/04/05/06). Phase 3 adds deeper error testing: malformed JSON body (400), missing jsonrpc field (400), invalid tool name (error in result), tool with bad arguments (error in result). All verified experimentally against SDK. |
| TEST-05 | HTTP-specific tests for concurrent requests (statelessness verification) | **Verified pattern works.** Three concurrent `list_form_fields` calls via `threading.Thread` within a single TestClient session all returned 200. No new dependencies needed. Test should verify: (a) all concurrent requests succeed, (b) each response contains correct tool output for its specific input, (c) no cross-contamination between concurrent calls. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| starlette (TestClient) | 0.52.1 | HTTP integration testing without starting a real server | Already installed, already used in Phase 2 tests. TestClient wraps the Starlette ASGI app and provides synchronous HTTP methods. |
| pytest | 9.0.2 | Test framework | Already installed, all existing tests use it. |
| threading | stdlib | Concurrent request testing | No external dependency. Threads are sufficient for concurrent TestClient requests since the TestClient handles synchronous blocking. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | Parse SSE response bodies and tool output text | Every test that reads a tool call result needs to parse SSE and then parse the JSON text content. |
| concurrent.futures | stdlib | Alternative to raw threading for cleaner concurrent patterns | Can use `ThreadPoolExecutor.map()` for concurrent tool calls if threading.Thread feels verbose. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Starlette TestClient | httpx.AsyncClient + ASGITransport | Would require pytest-asyncio (not installed). TestClient is simpler and already proven in Phase 2. |
| Threading for concurrency | asyncio + httpx async | Would require pytest-asyncio. Threading is simpler for this use case. |
| Direct function calls for "stdio" baseline | MCP client stdio transport | Would require spawning a subprocess, adding complexity. Direct function calls test the same code path and produce identical results. |

**Installation:**
No new packages needed. All dependencies already available.

## Architecture Patterns

### Recommended Project Structure
```
tests/
├── conftest.py                  # Shared fixtures: mcp_session, parse_sse_result, FIXTURES path
├── test_http_protocol.py        # EXISTING (Phase 2): 10 TRANS-03/04/05/06 protocol tests
├── test_http_transport_parity.py # NEW: TEST-02 transport parity (6 core tools)
├── test_http_utilities.py       # NEW: TEST-03 utility tools over HTTP
├── test_http_errors.py          # NEW: TEST-04 deeper HTTP error scenarios
├── test_http_concurrency.py     # NEW: TEST-05 concurrent request tests
├── test_e2e_integration.py      # EXISTING: direct function call e2e tests
└── ...                          # Other existing test files
```

### Pattern 1: Shared MCP Session Fixture (conftest.py)
**What:** A pytest fixture that creates a TestClient, initializes an MCP session, sends the `notifications/initialized` message, and yields a tuple of `(client, session_headers)` ready for tool calls.
**When to use:** Every test in test_http_transport_parity.py, test_http_utilities.py, test_http_concurrency.py.
**Why:** Eliminates duplicating 20+ lines of MCP handshake boilerplate in every test file. The `_fresh_app()` and `_reset_session_manager` patterns from Phase 2 are reused.
```python
# In conftest.py
import pytest
from starlette.testclient import TestClient
from src.mcp_app import mcp
from src.http_transport import _json_rpc_404_handler
import src.tools_extract  # noqa: F401
import src.tools_write    # noqa: F401

INIT_BODY = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"},
    },
}

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _fresh_app():
    mcp._session_manager = None
    app = mcp.streamable_http_app()
    app.exception_handlers[404] = _json_rpc_404_handler
    return app


@pytest.fixture(autouse=True)
def _reset_session_manager():
    yield
    mcp._session_manager = None


@pytest.fixture()
def mcp_session():
    """TestClient with initialized MCP session, ready for tool calls."""
    app = _fresh_app()
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Host": "localhost:8000"},
    ) as client:
        resp = client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
        assert resp.status_code == 200
        session_id = resp.headers.get("mcp-session-id")
        session_headers = {
            **MCP_HEADERS,
            "Mcp-Session-Id": session_id,
        }
        # Send initialized notification
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=session_headers,
        )
        yield client, session_headers
```
**Verified:** This exact pattern works. Tested experimentally.

### Pattern 2: SSE Response Parser Helper
**What:** A helper function that extracts the JSON-RPC result from an SSE response, then extracts the tool output JSON from `result.content[0].text`.
**When to use:** Every tool call assertion.
**Why:** SSE responses come as `event: message\ndata: {json}\n\n`. The tool result is nested inside `data.result.content[0].text` as a JSON string. Parsing this inline in every test would be verbose and error-prone.
```python
def parse_tool_result(response) -> dict:
    """Extract tool output dict from an SSE response to a tools/call request."""
    import json
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data:
                content = data["result"].get("content", [])
                if content and content[0].get("type") == "text":
                    return json.loads(content[0]["text"])
    raise ValueError("No tool result found in SSE response")
```
**Verified:** This exact pattern produces output identical to direct function calls.

### Pattern 3: Tool Call Helper
**What:** A helper function that sends a JSON-RPC `tools/call` request and returns the raw response.
**When to use:** Every tool invocation in integration tests.
```python
def call_tool(client, headers, tool_name, arguments, request_id=99):
    """Send a JSON-RPC tools/call request and return the HTTP response."""
    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": request_id,
        "params": {"name": tool_name, "arguments": arguments},
    }
    return client.post("/mcp", json=body, headers=headers)
```

### Pattern 4: Transport Parity Assertion
**What:** Call a tool directly (simulating stdio) and over HTTP, then compare the outputs.
**When to use:** For each of the 6 core tools (TEST-02).
```python
def test_extract_structure_compact_parity(mcp_session):
    client, headers = mcp_session
    args = {"file_path": "tests/fixtures/table_questionnaire.docx"}

    # HTTP path
    resp = call_tool(client, headers, "extract_structure_compact", args)
    assert resp.status_code == 200
    http_result = parse_tool_result(resp)

    # Direct path (simulates stdio)
    from src.tools_extract import extract_structure_compact
    direct_result = extract_structure_compact(**args)

    assert http_result == direct_result
```
**Verified:** This exact comparison returns True for extract_structure_compact and list_form_fields.

### Pattern 5: Concurrent Requests via Threading
**What:** Spawn multiple threads that each call a different tool (or the same tool with different inputs) simultaneously, then verify all returned correct results.
**When to use:** TEST-05 concurrent request tests.
```python
import threading

def test_concurrent_tool_calls(mcp_session):
    client, headers = mcp_session
    results = {}
    errors = {}

    def worker(tool_name, args, key):
        try:
            resp = call_tool(client, headers, tool_name, args, request_id=hash(key) % 1000)
            results[key] = (resp.status_code, parse_tool_result(resp))
        except Exception as e:
            errors[key] = str(e)

    threads = [
        threading.Thread(target=worker, args=("list_form_fields", {"file_path": "tests/fixtures/table_questionnaire.docx"}, "word")),
        threading.Thread(target=worker, args=("list_form_fields", {"file_path": "tests/fixtures/vendor_assessment.xlsx"}, "excel")),
        threading.Thread(target=worker, args=("list_form_fields", {"file_path": "tests/fixtures/simple_form.pdf"}, "pdf")),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Concurrent call errors: {errors}"
    assert all(status == 200 for status, _ in results.values())
    # Verify each result is correct by comparing against direct call
```
**Verified:** This exact pattern works -- all three concurrent calls return 200 with correct results.

### Anti-Patterns to Avoid
- **Starting a real server:** Do NOT spawn uvicorn in a subprocess for tests. TestClient provides full HTTP testing without network overhead, port conflicts, or process management.
- **Using MCP client SDK for stdio baseline:** Direct function calls are simpler and test the exact same code path as `mcp.run()` in stdio mode. The MCP client SDK adds subprocess spawning complexity with no benefit.
- **Putting all integration tests in one file:** The 200-line limit requires splitting. test_e2e_integration.py is already at 699 lines (a violation). Don't repeat this.
- **Duplicating session setup in every test file:** Use conftest.py fixtures. The `_fresh_app()` + `_reset_session_manager` pattern from Phase 2 should be shared.
- **Hardcoding fixture paths:** Use `Path(__file__).parent / "fixtures"` consistently. Already established pattern in test_e2e_integration.py.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP testing against ASGI app | Custom HTTP client + socket server | `starlette.testclient.TestClient` | Handles ASGI lifespan, request/response encoding, header management. Already proven in Phase 2. |
| SSE response parsing | Full SSE parser library | Simple `line.startswith("data: ")` extraction | MCP responses are always single-event SSE. No need for a full SSE parser (reconnection, multi-event streams, event IDs). |
| MCP session handshake | Manual JSON-RPC message construction | Shared fixture with INIT_BODY constant | Same handshake needed in every test. Extract once into conftest.py. |
| Concurrent request orchestration | asyncio event loop + httpx | `threading.Thread` + TestClient | TestClient is synchronous. Threads provide clean concurrency without adding async test infrastructure (pytest-asyncio not installed). |

**Key insight:** The test infrastructure is simple because the SDK does the heavy lifting. The HTTP transport tests are just: (a) send JSON-RPC over TestClient, (b) parse SSE response, (c) compare result with direct call. No protocol implementation, no custom transport, no server management.

## Common Pitfalls

### Pitfall 1: Session Manager Single-Use Limitation
**What goes wrong:** Second test function that creates a TestClient gets RuntimeError because session manager was already consumed.
**Why it happens:** `StreamableHTTPSessionManager.run()` can only be called once per instance. Each `with TestClient(app) as client:` block starts lifespan which calls `run()`.
**How to avoid:** Reset session manager between tests: `mcp._session_manager = None` before creating a new app. Already solved in Phase 2 with `_fresh_app()` + `autouse` fixture. Share these via conftest.py.
**Warning signs:** RuntimeError in second or later test, "session manager already running."

### Pitfall 2: Forgetting notifications/initialized After Initialize
**What goes wrong:** Tool calls return errors or hang.
**Why it happens:** The MCP protocol requires clients to send `notifications/initialized` after the initialize handshake before making tool calls. Some SDK versions enforce this.
**How to avoid:** Always send the notification in the session fixture, after the initialize response.
**Warning signs:** Tool calls returning unexpected errors or 400 status.

### Pitfall 3: SSE Response Format Varies by Request Type
**What goes wrong:** Tests assume all responses are JSON but some are SSE.
**Why it happens:** The SDK returns `Content-Type: text/event-stream` for tool calls and tools/list (streaming responses), but `Content-Type: application/json` for notifications (202 Accepted). The `initialize` response is SSE (200).
**How to avoid:** The `parse_tool_result()` helper handles SSE format. Do not call `resp.json()` on tool call responses -- always parse as SSE text.
**Warning signs:** `json.JSONDecodeError` on `resp.json()` calls.

### Pitfall 4: Tool Arguments Must Be Strings (Even When Not)
**What goes wrong:** Tool arguments that should be lists (like `locations` for `validate_locations`) need to be passed as JSON-compatible types.
**Why it happens:** The MCP `tools/call` params take `arguments: dict[str, Any]` -- the values are JSON-serialized by the transport. Complex types (lists, nested dicts) work naturally when passed via JSON-RPC.
**How to avoid:** Just pass arguments as Python dicts/lists. TestClient JSON-serializes them. This works correctly.
**Warning signs:** None -- this works naturally. Mentioned to prevent over-engineering.

### Pitfall 5: write_answers Parity Requires output_file_path
**What goes wrong:** Transport parity comparison fails because HTTP response contains base64 bytes string while direct call returns a dict with `file_bytes_b64`.
**Why it happens:** Both paths return the same dict structure (`{"file_bytes_b64": "..."}` or `{"file_path": "..."}`), but the base64 string is a large opaque blob. Comparing dicts directly works but is fragile for the b64 path.
**How to avoid:** Use `output_file_path` in both calls so both return `{"file_path": "/tmp/..."}`. Then compare the written file bytes independently. Or: compare the dict structures (they are identical) and optionally verify the b64 decodes to valid document bytes.
**Warning signs:** Tests passing but comparing multi-MB base64 strings (slow, noisy on failure).

### Pitfall 6: File Limit Enforcement (200 Lines)
**What goes wrong:** A test file grows beyond 200 lines, violating the project convention.
**Why it happens:** Integration tests are inherently verbose (setup, call, parse, compare). The 6-tool parity test plus helpers could easily hit 200 lines in a single file.
**How to avoid:** Split by concern: parity tests in one file, utility tests in another, error tests in another, concurrency in another. Move shared helpers to conftest.py. Each file stays focused and under 200 lines.
**Warning signs:** Line count exceeding 180 during implementation.

## Code Examples

Verified patterns from experimental testing against the installed SDK and Starlette:

### Complete Tool Call Over HTTP (verified experimentally)
```python
# Source: Verified via experimental testing against mcp==1.26.0 + starlette==0.52.1
import json

def call_tool(client, headers, tool_name, arguments, request_id=99):
    """Send a JSON-RPC tools/call request."""
    body = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": request_id,
        "params": {"name": tool_name, "arguments": arguments},
    }
    return client.post("/mcp", json=body, headers=headers)


def parse_tool_result(response) -> dict:
    """Extract tool output dict from SSE response."""
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data:
                content = data["result"].get("content", [])
                if content and content[0].get("type") == "text":
                    return json.loads(content[0]["text"])
    raise ValueError("No tool result found in SSE response")
```

### Transport Parity Test (verified experimentally)
```python
# Source: Verified -- outputs are byte-for-byte identical between HTTP and direct calls
def test_extract_compact_parity(mcp_session):
    client, headers = mcp_session

    resp = call_tool(client, headers, "extract_structure_compact", {
        "file_path": "tests/fixtures/table_questionnaire.docx",
    })
    assert resp.status_code == 200
    http_result = parse_tool_result(resp)

    from src.tools_extract import extract_structure_compact
    direct_result = extract_structure_compact(
        file_path="tests/fixtures/table_questionnaire.docx",
    )

    assert http_result == direct_result
```

### Malformed JSON-RPC Error (verified experimentally)
```python
# Source: Verified -- SDK returns 400 with JSON-RPC error body
# Malformed JSON body:
resp = client.post("/mcp", content=b"{broken", headers=MCP_HEADERS)
# Returns: 400, {"jsonrpc":"2.0","id":"server-error","error":{"code":-32700,"message":"Parse error: ..."}}

# Missing jsonrpc field:
resp = client.post("/mcp", json={"method": "initialize", "id": 1}, headers=MCP_HEADERS)
# Returns: 400, {"jsonrpc":"2.0","id":"server-error","error":{"code":-32602,"message":"Validation error: ..."}}
```

### Concurrent Requests (verified experimentally)
```python
# Source: Verified -- all three concurrent requests return 200 with correct results
import threading

def test_concurrent(mcp_session):
    client, headers = mcp_session
    results = {}

    def worker(key, file_path):
        resp = call_tool(client, headers, "list_form_fields", {"file_path": file_path})
        results[key] = parse_tool_result(resp)

    threads = [
        threading.Thread(target=worker, args=("word", "tests/fixtures/table_questionnaire.docx")),
        threading.Thread(target=worker, args=("excel", "tests/fixtures/vendor_assessment.xlsx")),
        threading.Thread(target=worker, args=("pdf", "tests/fixtures/simple_form.pdf")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(results) == 3
    # Verify each result matches direct call
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| httpx.AsyncClient + ASGITransport for ASGI testing | Starlette TestClient (synchronous, simpler) | Starlette 0.20+ (2022) | TestClient is the standard pattern for Starlette apps. Handles lifespan, cookies, redirects. |
| pytest-httpx / responses for HTTP mocking | Real ASGI transport via TestClient (no mocking needed) | N/A | No HTTP mocking needed since we test the ASGI app directly. More realistic tests. |
| SSE stream parsing with sseclient-py | Simple line parsing for single-event responses | N/A | MCP tool responses are always single SSE events. A full SSE library is overkill. |

**Deprecated/outdated:**
- `streamablehttp_client` (deprecated) -- use `streamable_http_client` (MCP SDK 1.26.0+). Not relevant for Phase 3 since we test server-side via TestClient, not via client SDK.

## Open Questions

1. **extract_text utility tool does not exist**
   - What we know: TEST-03 references `extract_text` as a utility to test over HTTP. The CLAUDE.md describes it as an optional utility. But no `@mcp.tool()` decorator for `extract_text` exists, no `text_extractor.py` handler exists.
   - What's unclear: Whether Phase 3 should implement it or skip it.
   - Recommendation: Skip `extract_text` testing for Phase 3. Test `list_form_fields` as the existing utility. Note the gap in test output. If `extract_text` is added later, add its HTTP test then.

2. **Whether test_http_protocol.py should be refactored to use shared fixtures**
   - What we know: Phase 2 created `test_http_protocol.py` with its own `_fresh_app()` and `_reset_session_manager` fixture. Phase 3 will add `conftest.py` with the same patterns. There will be duplication.
   - What's unclear: Whether to refactor Phase 2's file now or leave it isolated.
   - Recommendation: Move the shared patterns (`_fresh_app`, `_reset_session_manager`, `INIT_BODY`, `MCP_HEADERS`) into `conftest.py` and update `test_http_protocol.py` to use them. This deduplication is natural and reduces maintenance burden.

3. **What "identical results" means for write_answers and verify_output**
   - What we know: Tools that return document bytes (write_answers) or verification reports (verify_output) need input documents AND answer data. The parity test is more complex than read-only tools.
   - What's unclear: Whether byte-level identity is the right comparison for write_answers (document bytes could differ in metadata/timestamps even with same content).
   - Recommendation: For write_answers parity, compare the returned dict structure (not document bytes). For verify_output, compare the full verification report dict. Both should be identical since the underlying function is the same.

4. **conftest.py scope: tests/ root vs HTTP-specific**
   - What we know: The `mcp_session` fixture is only needed by HTTP tests, not by the existing unit tests.
   - What's unclear: Whether putting it in `tests/conftest.py` could affect existing tests (autouse fixtures apply to all tests in the directory).
   - Recommendation: Put `mcp_session` (non-autouse) in `tests/conftest.py`. The `_reset_session_manager` autouse fixture can safely apply to all tests -- it only does `mcp._session_manager = None` on cleanup, which is harmless for non-HTTP tests. If this causes issues, move HTTP fixtures to a `tests/http/conftest.py` subdirectory.

## Sources

### Primary (HIGH confidence)
- MCP Python SDK source code (installed `mcp==1.26.0`) -- `StreamableHTTPServerTransport`, `CallToolRequest`, `CallToolRequestParams`, `ClientSession.call_tool()` -- inspected via `inspect.getsource()`
- Starlette TestClient (installed `starlette==0.52.1`) -- verified behavior via experimental testing
- Experimental verification of transport parity: `extract_structure_compact`, `list_form_fields` called both directly and via HTTP TestClient, outputs confirmed identical
- Experimental verification of concurrent requests: 3 simultaneous `threading.Thread` calls via TestClient all returned 200 with correct results
- Experimental verification of error handling: malformed JSON (400), missing jsonrpc field (400), both return proper JSON-RPC error bodies

### Secondary (MEDIUM confidence)
- Phase 2 research (02-RESEARCH.md) -- TestClient pitfalls, session manager patterns, error response matrix
- Phase 2 implementation (02-01-SUMMARY.md) -- session manager reset pattern, fresh app helper, Host header requirement

### Tertiary (LOW confidence)
- None. All findings verified via experimental testing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already installed and verified. No new dependencies.
- Architecture: HIGH -- Every pattern verified experimentally. Transport parity confirmed. Concurrent requests confirmed. SSE parsing confirmed.
- Pitfalls: HIGH -- All pitfalls either inherited from Phase 2 (where they were discovered empirically) or discovered during this research via experimental testing.

**Research date:** 2026-02-16
**Valid until:** 2026-03-16 (stable -- testing patterns don't change rapidly, SDK version is fixed)
