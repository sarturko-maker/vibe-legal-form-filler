# Pitfalls Research

**Domain:** MCP HTTP Transport & Cross-Platform AI Agent Integration
**Researched:** 2026-02-16
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: stdout Pollution Breaking stdio Tests

**What goes wrong:**
When adding HTTP transport to an existing stdio server, developers continue logging or printing diagnostic information to stdout, which corrupts the JSON-RPC message stream in stdio mode, causing all stdio tests to fail with parse errors.

**Why it happens:**
stdio transport requires that NOTHING be written to stdout except valid MCP messages. HTTP transport is more forgiving—stdout can be used freely since messages go over HTTP. Developers test HTTP mode first, see their debug prints working fine, then existing stdio tests break mysteriously.

**How to avoid:**
- Before adding HTTP transport, audit all code paths for stdout usage (print statements, logging.info with StreamHandler, etc.)
- Redirect ALL logs to stderr: `logging.basicConfig(stream=sys.stderr)`
- In Python FastMCP: use structured logging to stderr ONLY
- Add a pre-commit hook: `grep -r "print(" python/` to catch new print statements
- Document in contribution guidelines: "NEVER use stdout directly"

**Warning signs:**
- Stdio tests pass locally but fail in CI after HTTP work
- Error messages like "Invalid JSON-RPC message" or "unexpected character at position 0"
- Tests fail only when verbose logging is enabled
- Message parsing works initially then breaks after innocent "debug print" commits

**Phase to address:**
Phase 1: Transport Setup (pre-implementation checklist)

---

### Pitfall 2: Missing Accept Header Causing 406 Errors

**What goes wrong:**
MCP servers strictly enforce the Accept header requirement. Clients that don't send `Accept: application/json, text/event-stream` receive HTTP 406 Not Acceptable errors. This breaks cross-platform compatibility with clients like Gemini CLI or Antigravity that may use different header configurations.

**Why it happens:**
The MCP spec mandates both content types in the Accept header for POST requests. Many HTTP clients default to `Accept: */*` or `Accept: application/json` only. SDK version 1.25.x+ introduced strict validation that rejects wildcards and single content types. Python SDK and TypeScript SDK implementations differ in strictness.

**How to avoid:**
- Client-side: Always send `Accept: application/json, text/event-stream` for POST to /mcp endpoint
- Server-side: For localhost-only v1, consider accepting wildcards (`*/*`, `application/*`) per HTTP/1.1 spec (RFC 7231)
- Test with multiple clients (Claude Code, Gemini CLI, Antigravity) BEFORE declaring compatibility
- Add integration tests that verify header handling with different Accept values
- Document required headers in README with examples for curl/httpie/requests library

**Warning signs:**
- Works with Claude Code but fails with Gemini CLI
- HTTP 406 errors in logs
- "Not Acceptable" responses during initialization
- Client reports "connection refused" but server shows 406 in access logs
- Works with custom test client but fails with production AI clients

**Phase to address:**
Phase 2: Protocol Implementation (header validation logic)
Phase 4: Cross-Platform Testing (multi-client validation)

---

### Pitfall 3: Session Management Confusion (Stateful vs Stateless)

**What goes wrong:**
Server implements stateful sessions with `Mcp-Session-Id` but then tries to scale horizontally with load balancing. Requests from the same client hit different server instances, which don't recognize the session ID, returning HTTP 404 Not Found. Client enters initialization loop, repeatedly creating new sessions.

**Why it happens:**
stdio transport has implicit session management (one process per client). HTTP requires explicit choice: stateful (session IDs + sticky routing) or stateless (no session IDs, each request independent). Developers default to stateful because it "feels like stdio" but forget about deployment implications.

**How to avoid:**
- For localhost-only v1: Skip session management entirely (stateless=True in FastMCP)
- If you implement sessions: Add LOUD warning in deployment docs about sticky sessions requirement
- Use `stateless_http=True` in FastMCP unless you have specific session requirements
- Test with 2+ server instances behind nginx/caddy to verify session handling breaks without sticky routing
- Document: "This server is stateless. Each request is independent. No session affinity needed."

**Warning signs:**
- Works in development (single server) but fails in production (load balanced)
- Intermittent "Session not found" errors
- Client repeatedly re-initializes
- Session IDs in logs but no session storage backend
- Server generates `Mcp-Session-Id` header but doesn't validate it on subsequent requests
- "Works 50% of the time" reports from users (round-robin hitting session-aware vs fresh instances)

**Phase to address:**
Phase 1: Transport Setup (architecture decision: stateful vs stateless)
Phase 3: Deployment Configuration (if stateful, add sticky session docs)

---

### Pitfall 4: Base64 Encoding Mismatch for Binary Files

**What goes wrong:**
Server encodes binary file data with `base64.urlsafe_b64encode()` (Python MCP SDK default) but client validator expects standard base64. Files decode correctly for small files but fail validation with "Invalid base64" errors for larger files containing `+` or `/` characters (which urlsafe converts to `-` and `_`).

**Why it happens:**
Python MCP SDK's BlobResourceContents uses `base64.urlsafe_b64encode()` for encoding but standard base64 validation for decoding. The spec doesn't explicitly require URL-safe encoding, but the Python SDK implementation assumes it. Only surfaces on larger binary files because small files are less likely to contain characters that differ between standard and URL-safe encoding.

**How to avoid:**
- For file_bytes_b64 input: Accept BOTH standard and URL-safe base64 (decode wrapper that tries both)
- For file_bytes_b64 output: Use standard base64.b64encode(), not urlsafe variant
- Add test case with binary file containing `+/` characters (e.g., image file > 1KB)
- Document in tool descriptions: "Binary data must be standard base64 encoded"
- Validate encoding in CI: decode sample files to verify no validation errors

**Warning signs:**
- Small files (< 1KB) work but larger files fail
- Error message mentions "Invalid base64" or character encoding
- Works with text files but fails with images/PDFs
- Validation passes in one SDK but fails in another (Python SDK vs TypeScript SDK)
- Base64 string length is correct but content doesn't decode

**Phase to address:**
Phase 2: Protocol Implementation (base64 encoding/decoding wrapper)
Phase 4: Cross-Platform Testing (test with multiple SDKs)

---

### Pitfall 5: Protocol Version Header Mismatch

**What goes wrong:**
Client sends `MCP-Protocol-Version: 2025-06-18` but server only supports `2024-11-05`. Server returns 400 Bad Request or silently falls back to old version. Client assumes new features (like streamable HTTP single endpoint) are available but server expects old HTTP+SSE dual-endpoint pattern. Connection fails or messages are silently dropped.

**Why it happens:**
Protocol version negotiation happens during initialization via JSON-RPC, but HTTP transport ALSO requires `MCP-Protocol-Version` header on every request. Developers implement one but not the other. Clients may send header before version negotiation completes. Servers may not validate header against negotiated version.

**How to avoid:**
- Server: Validate `MCP-Protocol-Version` header on ALL HTTP requests after initialization
- Server: Return 400 Bad Request with clear error message: "Unsupported protocol version: X. Server supports: Y."
- Server: If missing header and no negotiation yet, assume 2025-03-26 per spec fallback
- Client: Store negotiated version after initialization, send it in header on all subsequent requests
- Add integration test: client with mismatched version header should fail gracefully with clear error
- Log protocol version mismatches at ERROR level with both client and server versions

**Warning signs:**
- "Connection Error" with no details
- Works with Claude Code but fails with older clients
- Server logs show 400 Bad Request for initialization
- Client repeatedly retries initialization
- Features work inconsistently (SSE sometimes streams, sometimes returns single JSON)
- No version header in client HTTP requests

**Phase to address:**
Phase 2: Protocol Implementation (version validation middleware)
Phase 4: Cross-Platform Testing (test with clients on different protocol versions)

---

### Pitfall 6: SSE Stream Disconnection Without Resumability

**What goes wrong:**
During long-running tool execution (e.g., processing large document), SSE stream disconnects due to network timeout or proxy timeout. Server continues processing, returns response on closed stream. Client never receives result, thinks request timed out, retries from scratch. Server processes same request twice.

**Why it happens:**
SSE is persistent HTTP connection—proxies, load balancers, and clients all have timeout limits (often 60s). Streamable HTTP spec supports resumability via `Last-Event-ID` header but most servers don't implement it. Developers test with fast operations (< 5s) so never encounter disconnection during processing.

**How to avoid:**
- For v1 localhost: Document timeout limits clearly (60s default)
- Add connection keepalive: Send SSE comment (`: ping\n\n`) every 15s to prevent proxy timeout
- Implement idempotency: Tool calls with same args within 5min return cached result instead of re-processing
- Add request ID to tool call, server caches results by ID for 5min
- OR: Don't use SSE for long operations—return 202 Accepted immediately, provide status endpoint
- Test with artificial 90s delay to verify disconnection behavior

**Warning signs:**
- "Request timeout" errors but server logs show successful completion
- Same tool called multiple times with identical args
- Works in local testing but fails in production behind proxy
- Client shows spinner forever even though server finished
- No SSE keepalive comments in stream dump
- Load balancer logs show 504 Gateway Timeout for long requests

**Phase to address:**
Phase 2: Protocol Implementation (SSE keepalive middleware)
Phase 3: Deployment Configuration (document timeout limits)

---

### Pitfall 7: Testing Only Happy Path, Not Transport-Specific Failures

**What goes wrong:**
All 172 existing tests pass. You add HTTP transport. Tests still pass (they use stdio in-memory mode). Deploy to production. HTTP clients encounter Content-Type errors, missing CORS headers, session ID validation issues. None were caught by tests.

**Why it happens:**
FastMCP's test utilities default to in-memory stdio mode for speed. Tests don't exercise actual HTTP server, HTTP headers, CORS, session management, or network-level failures. Test coverage metrics show 100% but it's testing stdio code paths, not HTTP code paths.

**How to avoid:**
- Add dedicated HTTP transport test suite (separate from stdio tests)
- Use `StreamableHttpTransport` in tests, not in-memory stdio
- Start actual HTTP server with `run_server_in_process` fixture
- Test specific HTTP failure modes:
  - Missing Accept header → 406 error
  - Missing MCP-Protocol-Version header → 400 error
  - Invalid session ID → 404 error
  - Malformed JSON-RPC → 400 error with error response
  - Disconnection during SSE stream → graceful handling
- Test with real HTTP client (httpx/requests), not test client
- Mark as integration tests (slower, but critical for HTTP transport)

**Warning signs:**
- All tests pass but production HTTP clients fail
- Test suite runs in < 5s (means no real HTTP server startup)
- No tests importing `StreamableHttpTransport` or `httpx`
- Test coverage high but no HTTP-specific assertions
- Tests mock HTTP behavior instead of testing real transport
- No tests for HTTP status codes, headers, or CORS

**Phase to address:**
Phase 2: Protocol Implementation (add HTTP integration tests)
Phase 4: Cross-Platform Testing (test with real AI clients)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skipping session management | Faster v1 implementation, simpler server | Can't add later without breaking clients, no horizontal scaling | **Acceptable for localhost-only v1** |
| Using `Access-Control-Allow-Origin: *` | Works immediately with all clients | Security vulnerability for local servers, DNS rebinding attack vector | **Never acceptable**, use specific origin or localhost only |
| Accepting wildcard Accept headers | Broader client compatibility | Not strictly spec-compliant, may break with strict future clients | **Acceptable for v1** if documented |
| Not implementing SSE resumability | Simpler server, faster iteration | Client retry storms on disconnection, wasted computation | **Acceptable for v1** with documented timeout limits |
| Mixing stdio and HTTP logging patterns | Easier debugging during migration | Breaks stdio mode silently, hard to track down | **Never acceptable** |
| Skipping Content-Type validation | Permissive server, fewer client errors | Accepts invalid payloads, harder to debug client issues | **Acceptable in development only** |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gemini CLI | Assuming same behavior as Claude Code | Test explicitly—Gemini sends different Accept headers, may not support SSE |
| Antigravity | Not testing MCP config installation flow | Verify full setup flow in Antigravity IDE, not just API calls |
| FastMCP + FastAPI | Mounting http_app breaks FastAPI TestClient | Separate test suites: stdio tests with in-memory, HTTP tests with real server |
| Chromebook Crostini | Binding to 127.0.0.1, expecting browser access | Use 0.0.0.0 or penguin.linux.test domain, enable port forwarding in ChromeOS settings |
| Load balancers | Assuming sticky sessions work by default | Explicitly configure cookie-based session affinity OR use stateless mode |
| Reverse proxies (nginx/caddy) | Not forwarding MCP headers | Preserve `Mcp-Session-Id` and `MCP-Protocol-Version` headers in proxy config |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Blocking tool execution in HTTP handler | Server handles only 1 request at a time, clients timeout waiting | Use async tools, run CPU-intensive work in thread pool | > 2 concurrent clients |
| No SSE keepalive | Clients disconnect silently after 60s | Send comment every 15s: `: ping\n\n` | Any operation > 60s |
| Re-encoding base64 on every request | High CPU usage, slow responses for binary files | Cache decoded bytes, decode once on upload | Files > 1MB |
| Not streaming large responses | Client receives nothing until complete, appears frozen | Stream results as SSE events during processing | Responses > 100KB |
| Synchronous HTTP transport in FastMCP | Blocks event loop, can't handle concurrent requests | Use async HTTP client (httpx.AsyncClient), async tool functions | > 5 concurrent clients |
| Large file in file_bytes_b64 | Request body > 100MB, server OOM | Use file_path parameter, read/write to disk; OR stream via resource URIs | Files > 10MB |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Not validating Origin header | DNS rebinding attack—remote website accesses local MCP server | Validate Origin, reject non-localhost origins for local servers |
| Binding to 0.0.0.0 by default | Server accessible from network, even if intended localhost-only | Default to 127.0.0.1, require explicit flag for 0.0.0.0 |
| No authentication on HTTP transport | Anyone on network can call tools | For v1 localhost: acceptable; for network: require token in header |
| Wildcard CORS (`Access-Control-Allow-Origin: *`) | Any website can call server, CSRF attacks | Use specific origin or no CORS (localhost-only doesn't need CORS) |
| Logging sensitive file contents | file_bytes_b64 contains private data, logs expose it | Truncate logs: `log.info(f"Processing file, size: {len(data)}")` not `log.info(data)` |
| No rate limiting | Client can DoS server with rapid tool calls | For localhost v1: acceptable; for network: implement rate limiting (10 req/min) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Generic "Connection Error" message | User doesn't know if it's network, auth, or version mismatch | Return detailed error: "Server requires MCP protocol version 2025-06-18 but client uses 2024-11-05" |
| No progress indication for long operations | User thinks server hung, cancels and retries | Stream progress events via SSE: `data: {"progress": 0.5, "status": "Processing page 50/100"}` |
| Silent failure when session expires | Client sends request, gets 404, no explanation | Return error response: "Session expired. Please reconnect." |
| Timeout without hint about operation cost | "Request timed out" after 60s but operation needs 5min | During initialization, advertise timeout: `"capabilities": {"timeout_seconds": 60}` |
| No indication of transport mode | User doesn't know if stdio or HTTP is active | Log at startup: "MCP server listening on http://127.0.0.1:8000/mcp (Streamable HTTP transport)" |

## "Looks Done But Isn't" Checklist

- [ ] **HTTP Transport**: Tests pass but only test stdio mode—add `StreamableHttpTransport` integration tests
- [ ] **Session Management**: Server generates session IDs but doesn't validate them on subsequent requests
- [ ] **CORS Headers**: Added `Access-Control-Allow-Origin` but not `Access-Control-Allow-Headers` (breaks preflight)
- [ ] **Protocol Version**: Server parses header but doesn't validate it against supported versions
- [ ] **SSE Streaming**: Returns SSE content-type but doesn't send keepalive, breaks on long operations
- [ ] **Error Responses**: Returns HTTP error codes but no JSON-RPC error body (client can't parse error)
- [ ] **Base64 Validation**: Accepts base64 input but doesn't validate length/padding (fails on decode)
- [ ] **Tool Idempotency**: Implements retry logic but same request ID causes duplicate processing
- [ ] **Graceful Shutdown**: Closes server but doesn't wait for in-flight requests (truncated responses)
- [ ] **Cross-Platform Testing**: Works with Claude Code but never tested with Gemini CLI or Antigravity
- [ ] **Chromebook Networking**: Binds to 127.0.0.1 but Crostini browser can't access it (needs penguin.linux.test)
- [ ] **Documentation**: README says "supports HTTP" but doesn't document endpoint URL, headers, or limitations

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| stdout pollution | LOW | 1. Redirect logging to stderr in all modules. 2. Add pre-commit hook. 3. Re-run stdio tests to verify. |
| Missing Accept header | LOW | 1. Update client to send both content types. 2. Add header validation test. 3. Deploy client update. |
| Session management confusion | MEDIUM | 1. Choose stateless or stateful. 2. If stateful: add session storage + sticky routing. 3. Update docs. 4. Add load balancer config example. |
| Base64 mismatch | LOW | 1. Standardize on base64.b64encode(). 2. Add decode wrapper accepting both. 3. Add test with large binary file. |
| Protocol version mismatch | LOW | 1. Add version validation middleware. 2. Return clear error message. 3. Log both client and server versions. |
| SSE disconnection | MEDIUM | 1. Add SSE keepalive (15s interval). 2. Implement idempotency with request ID. 3. Document timeout limits. |
| No HTTP integration tests | MEDIUM | 1. Create HTTP test suite with real server. 2. Test failure modes (406, 400, 404). 3. Add to CI. Est: 4-6 hours. |
| CORS misconfiguration | LOW | 1. Remove wildcard origin. 2. Add origin validation. 3. Test with browser client. 4. Update CORS headers for preflight. |
| Chromebook networking | LOW | 1. Change bind address to 0.0.0.0. 2. Use penguin.linux.test URL. 3. Enable port forwarding in ChromeOS. 4. Document in README. |
| Breaking existing tests | HIGH | 1. Isolate stdio tests from HTTP changes. 2. Add transport-specific test suites. 3. Verify 172 tests still pass. 4. Add HTTP tests separately. Est: 8-12 hours. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| stdout pollution | Phase 1: Transport Setup | Run existing 172 stdio tests—all must pass |
| Missing Accept header | Phase 2: Protocol Implementation | Test with curl: send invalid Accept → 406 error |
| Session management confusion | Phase 1: Transport Setup | Document stateless mode, add test with 2 server instances |
| Base64 mismatch | Phase 2: Protocol Implementation | Test with 5MB binary file (image), verify decode succeeds |
| Protocol version mismatch | Phase 2: Protocol Implementation | Send wrong version header → 400 error with clear message |
| SSE disconnection | Phase 2: Protocol Implementation | Test with 90s operation, verify keepalive prevents disconnect |
| No HTTP integration tests | Phase 2: Protocol Implementation | Add HTTP test suite, verify 100% pass, run in CI |
| CORS misconfiguration | Phase 3: Deployment Configuration | Test from browser, verify preflight succeeds |
| Chromebook networking | Phase 3: Deployment Configuration | Test from ChromeOS browser with penguin.linux.test |
| Breaking existing tests | Phase 2: Protocol Implementation | CI gate: all 172 tests must pass before merge |
| Gemini CLI compatibility | Phase 4: Cross-Platform Testing | Connect from Gemini CLI, call tool, verify response |
| Antigravity compatibility | Phase 4: Cross-Platform Testing | Install MCP config in Antigravity, verify tool execution |

## Sources

- [Implementing MCP: Tips, Tricks and Pitfalls | Nearform](https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/)
- [MCP Transports Specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [Exploring the Future of MCP Transports](http://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/)
- [MCP Server Transports: STDIO, Streamable HTTP & SSE | Roo Code](https://docs.roocode.com/features/mcp/server-transports)
- [One MCP Server, Two Transports: STDIO and HTTP | Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/one-mcp-server-two-transports-stdio-and-http/4443915)
- [MCP Transport Protocols: stdio vs SSE vs StreamableHTTP | MCPcat](https://mcpcat.io/guides/comparing-stdio-sse-streamablehttp/)
- [FastMCP Running Your Server](https://gofastmcp.com/deployment/running-server)
- [Building StreamableHTTP MCP Servers - Production Guide | MCPcat](https://mcpcat.io/guides/building-streamablehttp-mcp-server/)
- [FastMCP HTTP Deployment](https://gofastmcp.com/deployment/http)
- [Managing Stateful MCP Server Sessions | CodeSignal](https://codesignal.com/learn/courses/developing-and-integrating-an-mcp-server-in-typescript/lessons/stateful-mcp-server-sessions)
- [State, and long-lived vs. short-lived connections | MCP Discussion](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/102)
- [Authentication and Authorization in MCP | Stack Overflow Blog](https://stackoverflow.blog/2026/01/21/is-that-allowed-authentication-and-authorization-in-model-context-protocol)
- [The MCP Ecosystem Has a Security Problem | Medium](https://medium.com/@debusinha2009/the-mcp-ecosystem-has-a-security-problem-c2f585a5bb05)
- [CORS Policies for Web-Based MCP Servers | MCPcat](https://mcpcat.io/guides/implementing-cors-policies-web-based-mcp-servers/)
- [MCP Base64 Encode/Decode Mismatch | GitHub Issue](https://github.com/modelcontextprotocol/python-sdk/issues/342)
- [Issue with HTTP Request Context Access in MCP | GitHub Issue](https://github.com/jlowin/fastmcp/issues/1233)
- [FastMCP Tests Documentation](https://gofastmcp.com/development/tests)
- [Port Forwarding | ChromeOS.dev](https://chromeos.dev/en/web-environment/port-forwarding)
- [Accessing Ports Between Crostini and ChromeOS – Coder.Haus](https://coder.haus/2019/03/11/accessing-ports-between-crostini-and-chromeos/)
- [Fix MCP Error -32001: Request Timeout | MCPcat](https://mcpcat.io/guides/fixing-mcp-error-32001-request-timeout/)
- [Error Handling in MCP Servers - Best Practices | MCPcat](https://mcpcat.io/guides/error-handling-custom-mcp-servers/)
- [Resilient AI Agents With MCP: Timeout And Retry Strategies | Octopus](https://octopus.com/blog/mcp-timeout-retry)
- [SSE Protocol Best Practices - MCP Server Documentation](https://mcp-cloud.ai/docs/sse-protocol/best-practices)
- [Improve DX for Protocol Version Negotiation Errors | GitHub Issue](https://github.com/modelcontextprotocol/inspector/issues/962)
- [MCP Versioning Specification](https://modelcontextprotocol.io/specification/versioning)
- [MCP Tool Validation Fails Due to Missing Accept Header | GitHub Discussion](https://github.com/open-webui/open-webui/discussions/19568)
- [MCP Server Won't Work with Wildcard Accept Header | GitHub Issue](https://github.com/modelcontextprotocol/python-sdk/issues/1641)
- [FastMCP Breaks FastAPI TestClient | GitHub Issue](https://github.com/jlowin/fastmcp/issues/2375)
- [Stop Vibe-Testing Your MCP Server | jlowin.dev](https://www.jlowin.dev/blog/stop-vibe-testing-mcp-servers)

---
*Pitfalls research for: MCP HTTP Transport & Cross-Platform AI Agent Integration*
*Researched: 2026-02-16*
