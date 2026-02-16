# Feature Research: MCP HTTP Transport & Cross-Platform Integration

**Domain:** MCP server with Streamable HTTP transport for cross-platform AI agent integration
**Researched:** 2026-02-16
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features clients assume exist. Missing these = platform won't connect or server is non-functional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Streamable HTTP POST endpoint** | MCP spec mandates single endpoint for all client messages | LOW | Must accept JSON-RPC requests with `Accept: application/json, text/event-stream` |
| **JSON-RPC 2.0 message format** | Universal MCP transport requirement | LOW | Already implemented in FastMCP |
| **MCP-Protocol-Version header** | Required by spec for HTTP transport | LOW | Client sends version (e.g., `2025-11-25`), server validates |
| **Session management (MCP-Session-Id)** | Most platforms expect stateful sessions | MEDIUM | FastMCP likely provides this; stateless servers can skip |
| **Origin header validation** | Security requirement (DNS rebinding protection) | MEDIUM | Prevents malicious websites from attacking localhost servers |
| **Localhost binding (127.0.0.1)** | Security best practice for local servers | LOW | Prevents exposure to network |
| **Graceful error responses** | Clients need actionable feedback | LOW | HTTP 400/404/405 with JSON-RPC error bodies |
| **Tool schema compliance** | All platforms validate against inputSchema | MEDIUM | Already implemented; ensure HTTP transport doesn't break it |
| **SSE stream support (optional)** | Some clients expect SSE for async responses | MEDIUM | Required for server-initiated messages; check FastMCP support |
| **Content-Type negotiation** | Clients send Accept header; server responds accordingly | LOW | `application/json` for single response, `text/event-stream` for SSE |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Transport parity (stdio + HTTP)** | Same tools work identically across both transports | HIGH | Core value proposition for this milestone |
| **Localhost-only with zero auth (v1)** | Simplest deployment for personal use | LOW | Defers auth complexity; differentiates from enterprise-focused servers |
| **Automatic transport detection** | Single entry point, mode flag chooses transport | MEDIUM | Better DX than separate binaries |
| **Detailed error context** | Rich error messages with file type, XPath, field IDs | LOW | Already implemented in tools; ensure HTTP transport preserves it |
| **Large payload optimization** | `answers_file_path` for writing >20 answers from JSON file | LOW | Already implemented; avoids overwhelming agent context windows |
| **Stateless design** | No session state between tool calls | LOW | Simplifies HTTP implementation; enables horizontal scaling later |
| **Multi-format support (Word/Excel/PDF)** | Most MCP servers are single-format | MEDIUM | Already implemented; HTTP transport expands reach |
| **Compact extraction** | Returns KB-sized indexed representation instead of MB OOXML | MEDIUM | Already implemented; critical for HTTP latency |
| **Comprehensive test coverage** | 172 unit tests + integration tests for transport parity | HIGH | Proves reliability across platforms |

### Anti-Features (Deliberately NOT Building)

Features that seem good but create problems for this milestone.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **API key auth (v1)** | "Localhost is insecure" | Adds complexity with no threat model (single user on Chromebook); premature for personal use | Defer to v2 for enterprise deployment; use Origin validation + localhost binding for v1 |
| **SSE-only transport** | Older HTTP+SSE spec | Deprecated as of 2024-11-05; Streamable HTTP is the new standard | Implement Streamable HTTP (POST+GET with optional SSE streams) |
| **Custom CORS policies** | "Need to connect from browser" | MCP servers don't serve browser clients; CORS is for same-origin policy | Origin validation is required; CORS configuration is not |
| **Rate limiting (v1)** | "Prevent abuse" | No abuse threat model for localhost-only personal use | Defer to v2 for multi-user deployments; rely on OS limits for v1 |
| **Websocket transport** | "Faster than HTTP" | Not in MCP spec; adds complexity with no measurable benefit | Streamable HTTP + SSE provides similar latency; stick to spec |
| **Multiple session support** | "Handle multiple clients" | Stateless design eliminates sessions; each tool call is independent | Each HTTP request is self-contained; no session state to manage |
| **Transport-specific optimizations** | "HTTP should batch operations" | Breaks transport parity; agent orchestrates batching, not server | Keep tool semantics identical across stdio and HTTP |
| **Embedded gateway/proxy** | "Route to multiple servers" | Scope creep; gateways are separate products | Focus on single-server HTTP transport; gateways are out of scope |

## Feature Dependencies

```
[Streamable HTTP POST endpoint]
    └──requires──> [JSON-RPC 2.0 message format] (already implemented)
    └──requires──> [MCP-Protocol-Version header] (new)
    └──requires──> [Origin header validation] (new)
    └──requires──> [Localhost binding] (new)

[Transport parity]
    └──requires──> [Streamable HTTP POST endpoint]
    └──requires──> [Integration tests] (stdio vs HTTP tool comparison)

[Session management]
    └──conflicts──> [Stateless design] (current architecture)
    └──optional──> [SSE stream support] (sessions enable stream resumption)

[Automatic transport detection]
    └──requires──> [Streamable HTTP POST endpoint]
    └──requires──> [Stdio transport] (already working)

[SSE stream support]
    └──enhances──> [Server-initiated messages] (not needed for stateless tools)
    └──optional──> [Resumable streams] (not needed for single-request tools)
```

### Dependency Notes

- **Streamable HTTP POST endpoint requires Origin validation:** The MCP spec explicitly requires DNS rebinding protection for localhost servers. Without Origin validation, a malicious website could send requests to `http://127.0.0.1:8000/mcp` and execute form-filling operations on the user's machine.
- **Transport parity requires both transports working:** The core value proposition is that tools work identically. This requires integration tests that send the same tool call (e.g., `extract_structure_compact`) over stdio and HTTP, then compare responses byte-for-byte.
- **Session management conflicts with stateless design:** The current server is stateless — each tool call is independent. Sessions add complexity (state storage, expiration, ID generation) with no benefit for this use case. However, some platforms (e.g., Copilot Studio) may expect session IDs. FastMCP likely handles this transparently.
- **SSE streams enhance server-initiated messages:** For stateless tools that always respond immediately, SSE provides no benefit. But if a future tool takes >30s to respond, SSE would allow streaming progress updates. Not needed for v1.

## MVP Recommendation

### Launch With (v1 — This Milestone)

Minimum viable HTTP transport to enable cross-platform MCP compatibility.

- [x] **Streamable HTTP POST endpoint** — Core requirement; single endpoint accepting JSON-RPC requests
- [x] **MCP-Protocol-Version header support** — Required by spec for HTTP transport
- [x] **Origin header validation** — Security requirement; prevents DNS rebinding attacks
- [x] **Localhost binding (127.0.0.1)** — Security best practice; prevents network exposure
- [x] **Transport mode flag (stdio vs HTTP)** — Single entry point, choose transport at startup
- [x] **JSON-RPC 2.0 format** — Already implemented in FastMCP; ensure HTTP preserves it
- [x] **Graceful error responses** — HTTP 400/404/405 with clear JSON-RPC error bodies
- [x] **Integration tests for transport parity** — Prove stdio and HTTP return identical results
- [x] **Cross-platform tests (Gemini CLI, Antigravity)** — Validate real-world platform compatibility

### Add After Validation (v1.x — Post-Launch)

Features to add once core HTTP transport is validated.

- [ ] **SSE stream support** — For platforms that expect streaming responses (e.g., long-running `write_answers` calls with 50+ answers)
- [ ] **Session management (MCP-Session-Id)** — If platforms reject stateless servers; FastMCP likely provides this
- [ ] **Detailed request/response logging** — For debugging cross-platform issues (trace IDs, timing)
- [ ] **Health check endpoint** — For deployment environments that need liveness probes
- [ ] **Swagger/OpenAPI spec** — For platforms like Copilot Studio that require it

### Future Consideration (v2+ — Enterprise Deployment)

Features to defer until enterprise deployment requirements are clear.

- [ ] **OAuth 2.1 authentication** — Standard for enterprise MCP servers as of 2025; replaces API keys
- [ ] **API key authentication (fallback)** — For platforms that don't support OAuth 2.1 yet
- [ ] **Rate limiting** — Per-client or per-tool limits to prevent abuse in multi-user environments
- [ ] **Observability (metrics, traces)** — Structured logging, distributed tracing, performance metrics
- [ ] **Gateway compatibility** — Work behind MCP gateways that provide centralized auth/logging
- [ ] **TLS support** — For remote deployment (not localhost)
- [ ] **Multi-session concurrency** — For servers handling multiple simultaneous clients
- [ ] **Prometheus metrics endpoint** — For infrastructure monitoring

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Streamable HTTP POST endpoint | HIGH | MEDIUM | P1 |
| Origin header validation | HIGH | LOW | P1 |
| Localhost binding | HIGH | LOW | P1 |
| MCP-Protocol-Version header | HIGH | LOW | P1 |
| Transport mode flag (stdio vs HTTP) | HIGH | LOW | P1 |
| Integration tests (transport parity) | HIGH | MEDIUM | P1 |
| Cross-platform tests (Gemini CLI, Antigravity) | HIGH | MEDIUM | P1 |
| Graceful error responses | MEDIUM | LOW | P1 |
| SSE stream support | MEDIUM | MEDIUM | P2 |
| Session management (MCP-Session-Id) | MEDIUM | LOW | P2 |
| Detailed logging | MEDIUM | LOW | P2 |
| Health check endpoint | LOW | LOW | P2 |
| Swagger/OpenAPI spec | MEDIUM | MEDIUM | P2 |
| OAuth 2.1 authentication | HIGH (enterprise) | HIGH | P3 |
| Rate limiting | MEDIUM (enterprise) | MEDIUM | P3 |
| Observability (metrics, traces) | HIGH (production) | HIGH | P3 |
| Gateway compatibility | MEDIUM | MEDIUM | P3 |
| TLS support | HIGH (remote) | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v1 launch (this milestone)
- P2: Should have, add when validated (v1.x)
- P3: Nice to have, defer to enterprise deployment (v2+)

## Platform-Specific Requirements

### Claude Code (stdio) — Already Working
- **Transport:** stdio (newline-delimited JSON-RPC)
- **Auth:** None (subprocess model)
- **Config:** `.claude/mcp.json` with `command` and `args`
- **Status:** Production-ready; 172 tests passing
- **Notes:** No changes needed; stdio transport remains unchanged

### Gemini CLI (HTTP) — Target Platform
- **Transport:** Streamable HTTP (`httpUrl` config)
- **Auth:** API key via `headers` (optional for v1)
- **Config:** `gemini mcp add -t http --url http://127.0.0.1:8000/mcp`
- **Constraints:** 500-tool limit per server (not a concern; we have 6 tools)
- **Notes:** Requires MCP-Protocol-Version header; likely expects session management

### Antigravity (HTTP) — Target Platform
- **Transport:** Streamable HTTP (`serverUrl` config, not `url`)
- **Auth:** API key via `headers` in `mcp_config.json` (optional for v1)
- **Config:** `.gemini/antigravity/mcp_config.json` (not `.cursor/mcp.json`)
- **Constraints:** Recommends <50 enabled tools for optimal performance (not a concern)
- **Notes:** Different config location than standard MCP clients; requires testing

### Copilot Studio (HTTP) — Deferred to Separate Milestone
- **Transport:** Streamable HTTP with Swagger 2.0 spec
- **Auth:** OAuth 2.0 or API key (required)
- **Config:** Native MCP onboarding wizard or Power Apps custom connector
- **Constraints:** Requires generative orchestration enabled; SSE deprecated (Streamable HTTP only)
- **Notes:** Requires enterprise credentials and network access not available on personal Chromebook; separate milestone

## Security Best Practices (Localhost v1)

| Practice | Implementation | Rationale |
|----------|---------------|-----------|
| **Bind to 127.0.0.1 only** | `host="127.0.0.1"` in HTTP server config | Prevents network exposure; only localhost processes can connect |
| **Validate Origin header** | Reject requests with invalid/missing Origin | Prevents DNS rebinding attacks from malicious websites |
| **Reject requests without MCP-Protocol-Version** | HTTP 400 for missing header | Enforces spec compliance; prevents ambiguous protocol versions |
| **No CORS AllowOrigin: *** | Do not set permissive CORS headers | MCP servers are not browser-accessible; CORS is irrelevant |
| **Log all rejected requests** | Log Origin, Protocol-Version, error reason | Helps debug platform integration issues |
| **No API key in v1** | Authentication deferred to v2 | No threat model for single-user localhost; premature optimization |
| **No TLS in v1** | Plain HTTP on localhost | TLS adds complexity with no security benefit for localhost-only |

## Performance Considerations

| Concern | v1 (Localhost) | v1.x (Validated) | v2+ (Enterprise) |
|---------|----------------|------------------|------------------|
| **Concurrent clients** | 1 (single user) | 1-5 (developer testing) | 10-100 (shared server) |
| **Request latency** | <500ms (local I/O) | <500ms (same) | <1s (remote network) |
| **Tool call duration** | 100ms-2s (document processing) | Same | Same |
| **Memory footprint** | <50MB (single process) | <100MB (potential SSE streams) | <500MB (multiple sessions) |
| **Horizontal scaling** | N/A (localhost) | N/A | Required (stateless enables load balancing) |

## Competitor Feature Analysis

| Feature | MCP Servers (General) | Firebase MCP Server | This Server (Form Filler) |
|---------|----------------------|---------------------|---------------------------|
| **Streamable HTTP transport** | Standard (2025 onwards) | Yes | v1 (this milestone) |
| **OAuth 2.1 auth** | Standard (enterprise) | Yes | v2 (deferred) |
| **SSE streams** | Common (server-initiated) | Yes | v1.x (optional) |
| **Session management** | Common (stateful servers) | Yes | v1.x (FastMCP provides) |
| **Origin validation** | Security best practice | Yes (CVE-2025-66414 fixed) | v1 (required) |
| **Localhost binding** | Security best practice | Yes | v1 (required) |
| **Stateless design** | Rare (most are stateful) | No (Firebase state) | Yes (architecture advantage) |
| **Multi-format support** | Rare (single-format common) | N/A (Firebase API) | Yes (Word/Excel/PDF) |
| **Transport parity** | Rare (most HTTP-only) | N/A (HTTP-only) | Yes (stdio + HTTP identical) |
| **Compact extraction** | Rare (most return raw data) | N/A | Yes (competitive advantage) |

## Sources

**MCP Specification & Transport:**
- [Transports - Model Context Protocol](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [HTTP Stream Transport | MCP Framework](https://mcp-framework.com/docs/Transports/http-stream-transport/)
- [MCP Server Transports: STDIO, Streamable HTTP & SSE | Roo Code Documentation](https://docs.roocode.com/features/mcp/server-transports)
- [Transport · Cloudflare Agents docs](https://developers.cloudflare.com/agents/model-context-protocol/transport/)
- [Exploring the Future of MCP Transports | Model Context Protocol Blog](http://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/)

**Platform Compatibility:**
- [MCP servers with the Gemini CLI | Gemini CLI](https://geminicli.com/docs/tools/mcp-server/)
- [How to connect MCP servers with Google Antigravity to maximize productivity - Composio](https://composio.dev/blog/howto-mcp-antigravity)
- [Connect your agent to an existing Model Context Protocol (MCP) server - Microsoft Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent)
- [Model Context Protocol (MCP) is now generally available in Microsoft Copilot Studio](https://www.microsoft.com/en-us/microsoft-copilot/blog/copilot-studio/model-context-protocol-mcp-is-now-generally-available-in-microsoft-copilot-studio/)

**Authentication & Security:**
- [Understanding Authorization in MCP - Model Context Protocol](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [MCP Authentication & Authorization: Guide for 2026](https://www.infisign.ai/blog/what-is-mcp-authentication-authorization)
- [Migrate from API keys to OAuth 2.1: Secure M2M authentication for AI agents](https://www.scalekit.com/blog/migrating-from-api-keys-to-oauth-mcp-servers)
- [Agentic Danger: DNS Rebinding Exposes Internal MCP Servers | Straiker](https://www.straiker.ai/blog/agentic-danger-dns-rebinding-exposing-your-internal-mcp-servers)
- [DNS Rebinding Protection Disabled by Default in Model Context Protocol TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk/security/advisories/GHSA-w48q-cv73-mx4w)

**Observability & Best Practices:**
- [MCP Server Observability: Monitoring, Testing & Performance Metrics | Zeo](https://zeo.org/resources/blog/mcp-server-observability-monitoring-testing-performance-metrics)
- [MCP Server Best Practices for 2026](https://www.cdata.com/blog/mcp-server-best-practices-2026)
- [15 Best Practices for Building MCP Servers in Production - The New Stack](https://thenewstack.io/15-best-practices-for-building-mcp-servers-in-production/)
- [MCP Hosting: Complete Guide to Hosting MCP Servers (2026)](https://www.agent37.com/blog/mcp-hosting-complete-guide-to-hosting-mcp-servers)

**Session Management & State:**
- [Managing Stateful MCP Server Sessions | CodeSignal Learn](https://codesignal.com/learn/courses/developing-and-integrating-an-mcp-server-in-typescript/lessons/stateful-mcp-server-sessions)
- [State, and long-lived vs. short-lived connections · modelcontextprotocol discussion](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/102)
- [MCP Session Management: Best Practices & Configuration 2025](https://www.byteplus.com/en/topic/541419)

**Tool Discovery & Schema Validation:**
- [Tools - Model Context Protocol](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP JSON Schema Validation: Tools & Best Practices 2025](https://www.byteplus.com/en/topic/542256)
- [MCP tool schema: what it is, how it works, and examples](https://www.merge.dev/blog/mcp-tool-schema)

**Performance & Benchmarking:**
- [MCP Benchmark: Top MCP Servers for Web Access in 2026](https://aimultiple.com/browser-mcp)
- [Multi-Language MCP Server Performance Benchmark | TM Dev Lab](https://www.tmdevlab.com/mcp-server-performance-benchmark.html)
- [The 10 Best MCP Servers for Platform Engineers in 2026](https://stackgen.com/blog/the-10-best-mcp-servers-for-platform-engineers-in-2026)

---
*Feature research for: MCP HTTP transport & cross-platform integration*
*Researched: 2026-02-16*
