---
status: testing
phase: 01-transport-setup
source: [01-01-SUMMARY.md]
started: 2026-02-16T23:00:00Z
updated: 2026-02-16T23:00:00Z
---

## Current Test

number: 1
name: Default stdio mode unchanged
expected: |
  Running `python -m src.server` (no flags) starts the server in stdio mode exactly as before. No visible difference from pre-change behavior. Ctrl+C exits cleanly.
awaiting: user response

## Tests

### 1. Default stdio mode unchanged
expected: Running `python -m src.server` (no flags) starts the server in stdio mode exactly as before. No visible difference from pre-change behavior. Ctrl+C exits cleanly.
result: [pending]

### 2. HTTP transport starts and responds
expected: Running `python -m src.server --transport http` starts the server and prints uvicorn startup info showing it bound to 127.0.0.1:8000. Running `curl http://127.0.0.1:8000/` in another terminal gets a response (not connection refused).
result: [pending]

### 3. Custom port works
expected: Running `python -m src.server --transport http --port 9000` starts the server bound to port 9000 instead of 8000. Curl to port 9000 succeeds.
result: [pending]

### 4. Port conflict detection
expected: Start the HTTP server on port 8000, then in another terminal try starting a second instance on port 8000. The second instance prints `Error: Port 8000 is already in use. Try: --port 8001` and exits immediately (non-zero).
result: [pending]

### 5. Cross-flag validation
expected: Running `python -m src.server --port 9000` (without --transport http) prints `Error: --port and --host require --transport http` and exits non-zero. Server does NOT start.
result: [pending]

### 6. CLI help output
expected: Running `python -m src.server --help` shows --transport, --port, --host flags with descriptions mentioning env var names (MCP_FORM_FILLER_TRANSPORT, MCP_FORM_FILLER_PORT, MCP_FORM_FILLER_HOST) and usage examples in the epilog.
result: [pending]

### 7. Package entry point
expected: Running `python -m src --help` works identically to `python -m src.server --help` (via __main__.py).
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0

## Gaps

[none yet]
