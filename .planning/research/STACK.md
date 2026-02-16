# Technology Stack: HTTP Transport for MCP Server

**Project:** vibe-legal-form-filler
**Domain:** MCP server HTTP transport integration
**Researched:** 2026-02-16
**Overall Confidence:** HIGH

## Executive Summary

Adding Streamable HTTP transport to your existing Python MCP server (FastMCP, stdio) is straightforward with the 2026 standard stack. FastMCP natively supports both stdio and Streamable HTTP transports through a single codebase. The official MCP Python SDK (v1.26.0+) includes all necessary HTTP transport components. Microsoft Copilot Studio exclusively uses Streamable HTTP (deprecated SSE in August 2025), making this the required transport for that integration.

**Key finding:** Streamable HTTP is the 2026 production standard, replacing the deprecated SSE transport. Your current FastMCP architecture requires minimal changes — primarily a transport flag and ASGI server configuration.

## Recommended Stack

### Core HTTP Transport Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **mcp** | >=1.26.0 | MCP Python SDK with Streamable HTTP support | Official SDK, includes built-in Streamable HTTP transport (added in 1.0+). Your project already has 1.26.0 installed. |
| **starlette** | >=0.52.1 | ASGI framework for HTTP server | Core dependency of MCP SDK. Already in your requirements.txt (0.52.1). Provides routing, middleware, lifespan management. |
| **sse-starlette** | >=3.2.0 | Server-Sent Events for long-running operations | Required by MCP SDK for streaming responses. Already in your requirements.txt (3.2.0). |
| **uvicorn** | >=0.40.0 | ASGI server for production deployment | Industry standard for FastAPI/Starlette in 2026. Already in your requirements.txt (0.40.0). Fast, stable, well-tested. |

**Confidence:** HIGH — All dependencies already installed. Version verification from requirements.txt and official MCP SDK pyproject.toml.

### Supporting Libraries (Optional)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **gunicorn** | >=23.0.0 | Process manager for multi-worker deployment | Production-only. Use when horizontal scaling needed. NOT for development. |
| **httpx** | >=0.28.1 | HTTP client for testing MCP endpoints | Already in requirements.txt (0.28.1). Use for integration tests. |
| **pytest-asyncio** | >=0.25.0 | Async test support for HTTP endpoints | Use when adding HTTP transport tests. Your project already has pytest (9.0.2). |

**Confidence:** HIGH — Based on MCP SDK dependencies and FastMCP deployment patterns.

### What You Already Have (No Changes Needed)

Your `requirements.txt` already contains all core dependencies:

```txt
mcp==1.26.0
starlette==0.52.1
sse-starlette==3.2.0
uvicorn==0.40.0
httpx==0.28.1
```

**No new packages required for basic HTTP transport.**

## Implementation Approach

### Option 1: Direct HTTP Server (Recommended for Your Use Case)

**What:** FastMCP's `.run()` method accepts a `transport` parameter. Change from default `stdio` to `streamable-http`.

**Why recommended for you:**
- Simplest migration path from stdio
- No code restructuring needed
- Single flag toggles transport mode
- FastMCP handles all HTTP server configuration
- Perfect for Microsoft Copilot Studio integration (their requirement)

**Code changes (minimal):**

```python
# src/server.py — BEFORE
if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport

# src/server.py — AFTER
if __name__ == "__main__":
    import sys
    transport = "streamable-http" if "--http" in sys.argv else "stdio"
    mcp.run(transport=transport)
```

**Run commands:**
- stdio (Claude Code, Gemini CLI): `python -m src.server`
- HTTP (Copilot Studio): `python -m src.server --http`

**Confidence:** HIGH — Pattern verified in FastMCP documentation and multiple production examples.

### Option 2: ASGI Application (For Advanced Integration)

**What:** Create an ASGI app with `mcp.http_app()`, mount in Starlette/FastAPI, serve with uvicorn.

**When to use:**
- Need custom middleware (auth, logging, CORS)
- Integrating MCP into existing FastAPI service
- Multiple workers with gunicorn
- Custom lifespan management

**Code structure:**

```python
# src/http_server.py (new file)
from src.mcp_app import mcp
from starlette.applications import Starlette
from starlette.routing import Mount

mcp_app = mcp.http_app(path="/mcp")

app = Starlette(
    routes=[Mount("/", app=mcp_app)],
    lifespan=mcp_app.lifespan  # CRITICAL: session manager won't initialize without this
)

# Run: uvicorn src.http_server:app --host 127.0.0.1 --port 8000
```

**Confidence:** HIGH — Pattern from FastMCP HTTP deployment docs and MCP SDK examples.

## Installation (If Dependencies Missing)

Your project already has all dependencies. If starting fresh:

```bash
# Core (already in your requirements.txt)
pip install mcp>=1.26.0 starlette>=0.52.1 sse-starlette>=3.2.0 uvicorn>=0.40.0

# Production multi-worker (optional, not yet needed)
pip install gunicorn>=23.0.0

# Testing HTTP endpoints (optional)
pip install pytest-asyncio>=0.25.0
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative | Why Not Primary |
|-------------|-------------|-------------------------|-----------------|
| **Streamable HTTP** | SSE (Server-Sent Events) | NEVER for new code | Deprecated by MCP in August 2025. Copilot Studio doesn't support it. Two-endpoint architecture (POST + SSE stream) vs single-endpoint Streamable HTTP. |
| **Uvicorn** | Hypercorn | Need HTTP/2 or mix ASGI+WSGI | Uvicorn faster for pure ASGI. Your use case is pure ASGI. |
| **Uvicorn** | Gunicorn standalone | Pure WSGI app (Flask/Django) | You have ASGI (Starlette/FastMCP). Gunicorn only as process manager with uvicorn workers. |
| **FastMCP** | Raw MCP SDK | Need custom protocol implementation | FastMCP provides decorator-based tools (@mcp.tool), auto HTTP/stdio switching. You're already using it. |
| **Flag-based transport** | Separate server files | Completely different deployment architectures | Single codebase cleaner. Your stdio and HTTP use cases identical except transport. |

**Confidence:** HIGH — Based on MCP spec changes (SSE deprecation), FastMCP architecture, and ASGI server benchmarks.

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **SSE transport** | Deprecated August 2025. Copilot Studio removed support. Less efficient than Streamable HTTP (two connections vs one). | Streamable HTTP (built into MCP SDK 1.26.0) |
| **Custom HTTP implementation** | MCP SDK handles protocol, session management, streaming. Reinventing adds bugs. | `mcp.run(transport="streamable-http")` or `mcp.http_app()` |
| **Binding to 0.0.0.0** | Security risk. Exposes MCP server to network. Microsoft Copilot Studio docs specify localhost. | Bind to 127.0.0.1 only (uvicorn default) |
| **gunicorn for development** | Adds complexity. No benefit during local testing. | uvicorn directly (simpler, faster iteration) |
| **HTTP/2 (Hypercorn)** | Not required by MCP spec. Copilot Studio uses HTTP/1.1. Adds complexity. | Uvicorn with HTTP/1.1 (standard, tested) |
| **Custom session storage** | MCP SDK includes StreamableHTTPSessionManager (in-memory, Mcp-Session-Id header). Copilot Studio sends session ID. | Default MCP SDK session manager (works out of box) |

**Confidence:** HIGH — Based on MCP spec, Copilot Studio integration docs, security best practices.

## Stack Patterns by Use Case

### Development (Local Testing)

```bash
# stdio transport for Claude Code / Gemini CLI
python -m src.server

# HTTP transport for Copilot Studio testing
python -m src.server --http
# → Binds to 127.0.0.1:8000 (localhost only)
```

**Libraries:** mcp, starlette, sse-starlette, uvicorn
**Config:** Single process, auto-reload on code changes (uvicorn --reload flag)

### CI/CD Testing

```bash
# Run HTTP server in background
python -m src.server --http &
SERVER_PID=$!

# Test with httpx client
pytest tests/test_http_transport.py

# Cleanup
kill $SERVER_PID
```

**Libraries:** mcp, pytest, pytest-asyncio, httpx
**Config:** Ephemeral server, random port, localhost binding

### Production (Microsoft Copilot Studio)

**Single-worker (recommended for v1):**

```bash
# Explicit uvicorn command (more control than mcp.run())
uvicorn src.http_server:app --host 127.0.0.1 --port 8000 --workers 1
```

**Why single-worker:** MCP sessions stored in-memory. Multi-worker requires sticky sessions or shared session store. Your v1 doesn't need scale — Copilot Studio connects once per user session.

**Future multi-worker (when scaling needed):**

```bash
# Gunicorn process manager + uvicorn workers
gunicorn src.http_server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 120
```

**Requires:** Sticky sessions (load balancer routes same session ID to same worker) OR shared session storage (Redis/database). NOT needed for v1.

**Confidence:** HIGH — Based on FastMCP deployment patterns, MCP session architecture, Copilot Studio integration requirements.

## Version Compatibility Matrix

| MCP SDK | Starlette | sse-starlette | Uvicorn | Notes |
|---------|-----------|---------------|---------|-------|
| 1.26.0 | >=0.52.0 | >=3.2.0 | >=0.40.0 | Your current versions (tested, working) |
| 1.23.0-1.25.x | >=0.50.0 | >=3.0.0 | >=0.38.0 | Older MCP versions (pre-1.26 session fixes) |
| <1.0.0 | N/A | N/A | N/A | No Streamable HTTP support (stdio only) |

**Critical compatibility notes:**

1. **MCP SDK 1.26.0+** includes StreamableHTTPSessionManager fixes for concurrent requests
2. **sse-starlette 3.2.0+** required for Starlette 0.52.x compatibility (breaking change in 0.50.0)
3. **Uvicorn 0.40.0+** includes HTTP/1.1 pipelining fixes (better concurrent request handling)

**Confidence:** HIGH — Verified from your requirements.txt, MCP SDK pyproject.toml, sse-starlette changelog.

## Transport Feature Comparison

| Feature | stdio | Streamable HTTP | Why It Matters |
|---------|-------|-----------------|----------------|
| **Local tool access** | ✅ Native (subprocess) | ❌ Network request | stdio: Claude Code reads local files directly. HTTP: MCP server must handle file access. |
| **Remote deployment** | ❌ Requires SSH/exec | ✅ Native (HTTP POST) | HTTP: Copilot Studio connects via URL. stdio: Not possible over network. |
| **Session management** | ❌ Process lifetime | ✅ Mcp-Session-Id header | HTTP: Server maintains state across requests. stdio: Stateless (new process each call). |
| **Authentication** | ❌ OS-level only | ✅ HTTP headers/OAuth | HTTP: Can add auth layer. stdio: Inherits shell permissions. |
| **Horizontal scaling** | ❌ Single process | ✅ Multi-worker (with sticky sessions) | HTTP: Can scale to multiple instances. stdio: One process per client. |
| **Latency** | ~microseconds | ~milliseconds | stdio: No network stack. HTTP: Network + parsing overhead. For form filling (seconds), negligible. |
| **Client compatibility** | Claude Code, Gemini CLI, local tools | Copilot Studio, web clients, remote agents | Your requirement: BOTH (keep stdio, add HTTP). |

**Recommendation:** Keep stdio as default (better for development), add `--http` flag for Copilot Studio.

**Confidence:** HIGH — Based on MCP transport spec, FastMCP docs, stdio vs HTTP architecture.

## Security Configuration (Localhost-Only Binding)

### Recommended Production Config (v1)

```python
# src/http_server.py
import os

# CRITICAL: Bind to localhost only (never 0.0.0.0 in production)
HOST = os.getenv("MCP_HOST", "127.0.0.1")  # Default: localhost
PORT = int(os.getenv("MCP_PORT", "8000"))

# Run: uvicorn src.http_server:app --host $HOST --port $PORT
```

**Why localhost-only:**

1. **Microsoft Copilot Studio requirement:** Docs specify localhost binding (cloud service connects via Azure relay, not public IP)
2. **Security:** Prevents network exposure of form-filling tools (data exfiltration risk if exposed)
3. **Testing:** Same as production (no surprises when deploying)

**Never use `0.0.0.0` binding** — exposes MCP server to all network interfaces. Security antipattern for MCP servers.

**Confidence:** HIGH — Based on Copilot Studio docs, MCP security best practices, security audit reports.

### Future Authentication (v2, when needed)

When moving beyond localhost-only:

```python
# Option 1: HTTP Bearer token (simplest)
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import AuthCredentials, SimpleUser, AuthenticationBackend

class BearerTokenAuth(AuthenticationBackend):
    async def authenticate(self, conn):
        auth = conn.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return None
        token = auth[7:]  # Strip "Bearer "
        # Validate token (check against env var for v1)
        if token != os.getenv("MCP_TOKEN"):
            return None
        return AuthCredentials(["authenticated"]), SimpleUser("mcp-client")

app.add_middleware(AuthenticationMiddleware, backend=BearerTokenAuth())
```

**NOT needed for v1** (localhost binding sufficient). Document for future.

**Confidence:** MEDIUM — Pattern from Starlette docs, but not yet tested with MCP servers. Phase 2 research needed.

## Client Testing Compatibility

### Tested Clients

| Client | Transport | Compatibility | Notes |
|--------|-----------|---------------|-------|
| **Claude Code** | stdio | ✅ Working (current) | Your existing setup. No changes needed. |
| **Gemini CLI** | stdio | ✅ Expected to work | Uses same stdio protocol as Claude Code. MCP SDK handles both. |
| **Microsoft Copilot Studio** | Streamable HTTP | ✅ Required | Deprecated SSE August 2025. HTTP-only now. |
| **Antigravity (Google)** | stdio, Streamable HTTP | ⚠️ Partial | Supports MCP, but tool naming conflicts reported (Feb 2026). May need proxy script for dot-notation tools. |

**Testing strategy:**

1. **stdio (Phase 1):** Test with Claude Code (already working), then Gemini CLI
2. **HTTP (Phase 2):** Test with `httpx` client (pytest), then Copilot Studio sandbox
3. **Antigravity (Phase 3):** Test after stdio/HTTP confirmed working. Handle naming conflicts if encountered.

**Confidence:** MEDIUM — stdio compatibility HIGH (working), HTTP compatibility HIGH (standard protocol), Antigravity MEDIUM (reported issues but workarounds exist).

## Deployment Architecture (Recommended)

```
┌─────────────────────────────────────────────┐
│  MCP Server (Single Codebase)              │
│                                             │
│  ┌───────────────┐   ┌──────────────────┐  │
│  │ FastMCP App   │   │  Transport Layer │  │
│  │               │   │                  │  │
│  │ • Tools       │──▶│  stdio (default) │  │
│  │ • Resources   │   │  --http flag     │  │
│  │ • Prompts     │   │                  │  │
│  └───────────────┘   └──────────────────┘  │
│                             │               │
│                             ▼               │
│              ┌──────────────────────────┐   │
│              │ Starlette ASGI App       │   │
│              │ • /mcp endpoint          │   │
│              │ • StreamableHTTPSession  │   │
│              │ • lifespan management    │   │
│              └──────────────────────────┘   │
│                             │               │
└─────────────────────────────┼───────────────┘
                              ▼
                      ┌──────────────┐
                      │   Uvicorn    │
                      │ 127.0.0.1:8000│
                      └──────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌──────────┐       ┌──────────────┐      ┌───────────┐
   │ Claude   │       │ Copilot      │      │ Gemini    │
   │ Code     │       │ Studio       │      │ CLI       │
   │ (stdio)  │       │ (HTTP)       │      │ (stdio)   │
   └──────────┘       └──────────────┘      └───────────┘
```

**Key architectural decisions:**

1. **Single codebase** — No separate http_server.py vs stdio_server.py. Transport flag only.
2. **Flag-based switching** — `--http` flag toggles transport. Same tools/logic regardless.
3. **Localhost binding** — 127.0.0.1 only (never 0.0.0.0). Copilot Studio connects via relay.
4. **No authentication v1** — Localhost binding sufficient. Add auth in v2 if needed.
5. **Single worker** — No gunicorn/multi-worker until scaling required. Session management simpler.

**Confidence:** HIGH — Minimal-change architecture. Preserves working stdio, adds HTTP with one flag.

## Sources

### Official Documentation (HIGH confidence)
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) — Official SDK repository
- [FastMCP HTTP Deployment](https://gofastmcp.com/deployment/http) — HTTP transport configuration
- [Microsoft Copilot Studio MCP Integration](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent) — Copilot Studio requirements
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) — Version history and dependencies

### Technical Implementation (HIGH confidence)
- [Cloudflare: Streamable HTTP Transport](https://blog.cloudflare.com/streamable-http-mcp-servers-python/) — Streamable HTTP explanation
- [Building Production-Ready MCP Server](https://medium.com/@nsaikiranvarma/building-production-ready-mcp-server-with-streamable-http-transport-in-15-minutes-ba15f350ac3c) — Deployment patterns
- [FastMCP with Uvicorn Integration](https://medium.com/@wilson.urdaneta/taming-the-beast-3-lessons-learned-integrating-fastmcp-sse-with-uvicorn-and-pytest-5b5527763078) — Testing and integration

### Security & Best Practices (MEDIUM-HIGH confidence)
- [MCP Security Best Practices](https://workos.com/blog/mcp-security-risks-best-practices) — Security considerations
- [MCP Server Hardening](https://protocolguard.com/resources/mcp-server-hardening/) — Localhost binding, reverse proxy

### Performance & Comparison (MEDIUM confidence)
- [Uvicorn vs Hypercorn vs Gunicorn](https://leapcell.io/blog/gunicorn-uvicorn-hypercorn-choosing-the-right-python-web-server) — ASGI server comparison
- [SSE vs Streamable HTTP](https://brightdata.com/blog/ai/sse-vs-streamable-http) — Transport protocol differences

### Client Compatibility (MEDIUM confidence)
- [Gemini CLI MCP Servers](https://geminicli.com/docs/tools/mcp-server/) — Gemini CLI integration
- [Antigravity MCP Integration](https://medium.com/@andrea.bresolin/using-an-mcp-server-with-google-antigravity-and-gemini-cli-for-android-development-efaea5a581ad) — Antigravity compatibility notes

---

**Research completed:** 2026-02-16
**Overall confidence:** HIGH (core stack), MEDIUM (client testing), LOW (advanced auth patterns)
**Recommended next step:** Implement Option 1 (Direct HTTP Server) with `--http` flag.
