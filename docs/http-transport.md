# HTTP Transport

The MCP server supports two transport protocols: **stdio** (default) and **HTTP** (Streamable HTTP). This guide covers starting the server in HTTP mode, configuring the port and host, and connecting MCP clients to the endpoint.

## Starting the Server

From the project root:

```bash
python -m src.server --transport http
```

Expected output:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

The server runs in the foreground. Use a separate terminal for the MCP client.

## Endpoint

The MCP endpoint is served at `/mcp`:

```
http://127.0.0.1:8000/mcp
```

All MCP client configurations must include the `/mcp` path. Requests to the root `/` will return a 404 error.

## CLI Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--transport` | `stdio`, `http` | `stdio` | Transport protocol to use |
| `--port` | `1024`-`65535` | `8000` | Port for the HTTP server |
| `--host` | Any valid hostname/IP | `127.0.0.1` | Host/IP address to bind to |

Notes:

- `--port` and `--host` are only valid when `--transport http` is set. Using them with stdio will produce an error.
- Port values outside the 1024-65535 range are rejected.
- The server binds to `127.0.0.1` (localhost) by default. This means only local connections are accepted -- no authentication is needed for local use.

## Environment Variables

Each CLI flag has a corresponding environment variable fallback. CLI flags take precedence over environment variables.

| Environment Variable | Corresponding Flag | Default |
|---------------------|--------------------|---------|
| `MCP_FORM_FILLER_TRANSPORT` | `--transport` | `stdio` |
| `MCP_FORM_FILLER_PORT` | `--port` | `8000` |
| `MCP_FORM_FILLER_HOST` | `--host` | `127.0.0.1` |

Environment variables are used when the corresponding CLI flag is not provided. For example:

```bash
export MCP_FORM_FILLER_PORT=9000
python -m src.server --transport http
# Server starts on port 9000
```

A CLI flag always overrides the environment variable:

```bash
export MCP_FORM_FILLER_PORT=9000
python -m src.server --transport http --port 8080
# Server starts on port 8080 (CLI flag wins)
```

## Examples

**Default HTTP (localhost:8000):**

```bash
python -m src.server --transport http
# Endpoint: http://127.0.0.1:8000/mcp
```

**Custom port:**

```bash
python -m src.server --transport http --port 9000
# Endpoint: http://127.0.0.1:9000/mcp
```

**Custom host and port:**

```bash
python -m src.server --transport http --host 0.0.0.0 --port 9000
# Endpoint: http://0.0.0.0:9000/mcp
```

**Using environment variables:**

```bash
export MCP_FORM_FILLER_TRANSPORT=http
export MCP_FORM_FILLER_PORT=9000
python -m src.server
# Endpoint: http://127.0.0.1:9000/mcp
```

## Port Conflict Detection

The server checks whether the port is available before starting. If the port is already in use, it exits with a clear error:

```
Error: Port 8000 is already in use. Try: --port 8001
```

## Graceful Shutdown

Press `Ctrl+C` to stop the server. In-flight requests are given 5 seconds to complete before the server shuts down.

## Security Note

By default, the server binds to `127.0.0.1` (localhost only). This means only processes on the same machine can connect. No authentication mechanism is included -- this is appropriate for local development and personal use. If you bind to `0.0.0.0` (all interfaces), the server will be accessible from other machines on the network. Do not expose the server to untrusted networks without adding authentication.
