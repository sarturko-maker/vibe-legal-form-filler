# Technology Stack

**Analysis Date:** 2025-02-16

## Languages

**Primary:**
- Python 3.11+ - Server-side document manipulation, MCP protocol implementation

## Runtime

**Environment:**
- Python 3.11 or later (specified in `pyproject.toml`)

**Package Manager:**
- pip (standard Python package manager)
- Lockfile: present (`requirements.txt` with pinned versions)

## Frameworks

**Core:**
- MCP (Model Context Protocol) 1.26.0+ - Protocol framework for agent communication via FastMCP
- Pydantic 2.12.5+ - Data validation and serialization for all tool inputs/outputs

**Document Processing:**
- lxml 6.0.2+ - XML parsing and XPath queries for OOXML manipulation
- python-docx 1.2.0 - High-level Word (.docx) document API
- openpyxl 3.1.5+ - Excel (.xlsx) workbook reading and writing
- PyMuPDF (fitz) 1.27.1+ - PDF handling and AcroForm widget manipulation

**Testing:**
- pytest 9.0.2+ - Test runner and framework
- No dedicated mocking library in requirements (uses built-in unittest.mock)

**Build/Dev:**
- setuptools 68.0+ - Python package building

## Key Dependencies

**Critical:**
- mcp >= 1.26.0 - Protocol layer connecting this server to calling agents
- lxml >= 6.0.2 - Core XML parsing for all OOXML manipulation (Word format)
- openpyxl >= 3.1.0 - Cell-level Excel manipulation; critical for accurate R-C indexing
- pymupdf >= 1.24.0 - PDF widget extraction and field value manipulation
- pydantic >= 2.4.0 - Request/response validation for all MCP tools
- python-docx >= 1.0.0 - High-level Word document structure reading

**Infrastructure:**
- No database drivers
- No caching layer (stateless per-call)
- No message queue or async workers (synchronous tool calls only)
- No external service SDKs (self-contained document processing)

## Configuration

**Environment:**
- Not configured via environment variables
- No secrets or API keys required
- Stateless operation: each tool call is independent
- File paths accepted as input parameters (both absolute and relative)

**Build:**
- `pyproject.toml` - Python project metadata and dependencies
- `requirements.txt` - Pinned dependency versions for reproducible installs
- No build configuration files (pure Python)
- No Docker, no container runtime required

## Platform Requirements

**Development:**
- Python 3.11+
- Standard development tools (not specified, any OS supporting Python)

**Production:**
- Python 3.11 runtime
- Disk space for temporary file I/O (zipfile operations for .docx/.xlsx)
- RAM proportional to document size (loaded entirely into memory for processing)
- Runs as a local MCP server connected via stdio (no network listening)

## Entry Point

- `src/server.py` - MCP server entry point
  - Runs via: `python -m src.server`
  - Registers MCP tools from `src/tools_extract.py` and `src/tools_write.py` at import time
  - Connects to calling agent via FastMCP stdio transport

## No External Dependencies

**What is NOT used:**
- No REST API framework (uses MCP protocol only, not HTTP)
- No database (no persistent storage between calls)
- No cloud SDKs (AWS, Azure, GCP)
- No LLM APIs (Claude, OpenAI, etc. — all AI reasoning is agent-side)
- No authentication layer (trusts calling agent, no auth tokens)
- No caching service (Redis, Memcached)
- No message queue (RabbitMQ, SQS)
- No monitoring service (Sentry, DataDog)
- No logging service (all logs to stdout/stderr)
- No web framework (FastAPI, Flask, Django)
- No ORM (SQLAlchemy, etc.)

---

*Stack analysis: 2025-02-16*
