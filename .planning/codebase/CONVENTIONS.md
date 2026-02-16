# Coding Conventions

**Analysis Date:** 2025-02-16

## Naming Patterns

**Files:**
- Snake case for all files: `word_parser.py`, `excel_verifier.py`, `pdf_indexer.py`
- Module names describe their function or primary export: `xml_snippet_matching.py`, `word_element_analysis.py`, `build_insertion_xml.py`
- Handler modules use format prefix: `word.py`, `excel.py`, `pdf.py` (main entry points); specialized handlers: `word_parser.py`, `word_indexer.py`, `word_writer.py`
- Test files mirror source structure: `test_word.py` mirrors `src/handlers/word.py`, `test_excel_verifier.py` mirrors `src/handlers/excel_verifier.py`

**Functions:**
- Snake case with verb-first pattern: `extract_structure_compact()`, `validate_locations()`, `write_answers()`
- Private functions prefixed with `_`: `_parse_body()`, `_index_table()`, `_find_run_properties()`
- Helper functions suffixed with intent: `_get_cell_text()`, `_extract_formatting()`, `_verify_content()`
- No abbreviations in public function names: use `extract_structure` not `ext_struct`

**Variables:**
- Snake case for all variables: `file_bytes`, `id_to_xpath`, `complex_elements`
- Boolean variables prefixed with `is_`, `has_`, or `can_`: `is_well_formed`, `has_formatting`, `can_merge`
- Counter variables: `p_counter`, `t_counter`, `sheet_idx` (clear intent)
- Temporary/loop variables kept short: `ws` (worksheet), `cell` (when iterating), `elem` (element)

**Types:**
- PascalCase for all classes (Pydantic models, Enums): `CompactStructureResponse`, `LocationStatus`, `FileType`
- Enum names as UPPER_SNAKE_CASE: `REPLACE_CONTENT`, `PLAIN_TEXT`, `MATCHED`
- Type hints required everywhere (except trivial returns like `None`)

## Code Style

**Formatting:**
- No linter enforced; project is "vibe coded" (AI-assisted development)
- Follow PEP 8 conventions (120 character line length practical limit)
- Module docstrings at top of every file: `"""Purpose — what this module does and why it exists."""`
- Function docstrings required for all public functions: parameter list, return type, and usage context
- Example from `word_parser.py`:
  ```python
  def read_document_xml(file_bytes: bytes) -> bytes:
      """Extract word/document.xml from a .docx ZIP archive."""
  ```

**Comments:**
- Comments explain WHY, not WHAT. Code tells you what; comments explain reasoning or gotchas.
- Single-line comments for implementation notes: `# Secure parser — disables external entities (XXE prevention)`
- Comments on complex algorithms or counterintuitive choices only.
- No commented-out code; remove or delete instead.

## Import Organization

**Order (strict):**
1. `from __future__ import annotations` (always first, if used)
2. Standard library imports: `import zipfile`, `import re`, `from io import BytesIO`
3. Third-party imports: `from lxml import etree`, `import openpyxl`, `import fitz`
4. Relative imports: `from src.models import ...`, `from src.xml_utils import ...`
5. Blank line between each group

**Example from `word_indexer.py`:**
```python
from __future__ import annotations

import zipfile
from io import BytesIO

from lxml import etree

from src.models import CompactStructureResponse
from src.xml_utils import NAMESPACES, SECURE_PARSER, build_xpath
```

**Path Aliases:**
- No aliases needed; project uses flat relative imports from `src/`
- Always import from package root: `from src.handlers.word_indexer import extract_structure_compact`
- Barrel re-exports allowed: `from src.xml_utils import NAMESPACES, SECURE_PARSER` (re-exported from `xml_snippet_matching.py`)

**Wildcard imports:**
- Never use `from module import *`
- All imports explicit and named

## Module Design

**File size:**
- Strict limit: no file longer than ~200 lines
- When approaching limit, split into focused submodules
- Example: `word_indexer.py` (160 lines) + `word_element_analysis.py` (112 lines) instead of monolithic 270-line file

**Exports:**
- Each handler module (word.py, excel.py, pdf.py) exposes a consistent public API:
  - `extract_structure_compact()` — compact indexed representation
  - `extract_structure()` — raw/full structure
  - `validate_locations()` — confirm element IDs/snippets
  - `build_insertion_xml()` — (Word only) create OOXML from answer + formatting
  - `write_answers()` — insert answers into document
  - `verify_output()` — post-write validation
  - `list_form_fields()` — heuristic form field detection
- Implementation details imported from submodules, not exposed

**Barrel files:**
- `xml_utils.py` re-exports all XML utilities: `from src.xml_snippet_matching import ...` + `from src.xml_formatting import ...`
- Allows callers to do: `from src.xml_utils import NAMESPACES, build_run_xml, is_well_formed_ooxml` (single import)

## Function Design

**Size:**
- No function longer than 40 lines
- If function exceeds 40 lines, extract helper functions with clear names
- Example: `build_insertion_xml()` is ~25 lines; complex logic moved to `_find_run_properties()`, `_extract_formatting()`, `_apply_*()` helpers

**Parameters:**
- Maximum 3-4 parameters; use Pydantic models for complex inputs
- Example: `validate_locations(file_bytes: bytes, locations: list[LocationSnippet])` not 6 separate params
- No boolean flags for mode switching; use Enums: `InsertionMode.REPLACE_CONTENT` not `replace=True`

**Return Values:**
- Return single value or tuple only (no out-parameters)
- For multiple related values, return Pydantic model: `CompactStructureResponse(compact_text=..., id_to_xpath=..., complex_elements=...)`
- All public functions have return type hints

## Error Handling

**Pattern: raise or return error:**
- Parser/indexer functions raise exceptions on malformed input: `raise ValueError("No <w:body> element found")`
- Validation functions return error status in response object: `ValidatedLocation(status=LocationStatus.NOT_FOUND, context=None)`
- Writer functions raise on structural issues: `raise ValueError("Invalid cell ID: {cell_id}")`

**Error messages:**
- Include context: `ValueError("Invalid cell ID: S1-R2-Z5 (Z invalid)")` not `ValueError("Bad cell ID")`
- Use f-strings: `f"Unknown namespace: {uri}"` not `"Unknown namespace: " + uri`

**No silent failures:**
- Parsing always validates: `if body is None: raise ValueError(...)`
- No `return None` without comment explaining why it's expected
- XML operations wrapped in try/except with clear error propagation

**Example from `xml_formatting.py`:**
```python
def _parse_element_xml(element_xml: str) -> etree._Element:
    """Parse an OOXML element string, adding namespace wrappers if needed."""
    try:
        return etree.fromstring(element_xml.encode("utf-8"), SECURE_PARSER)
    except etree.XMLSyntaxError:
        wrapper = f'<_wrapper xmlns:w="{NAMESPACES["w"]}" ...>{element_xml}</_wrapper>'
        return etree.fromstring(wrapper.encode("utf-8"), SECURE_PARSER)[0]
```

## Validation & Constants

**Constants:**
- All-caps SCREAMING_SNAKE_CASE at module level
- Centralized in one place; imported everywhere else
- OOXML namespaces centralized in `xml_snippet_matching.py`:
  ```python
  NAMESPACES = {
      "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
  }
  ```
- OOXML element whitelist in `xml_validation.py`:
  ```python
  _ALLOWED_OOXML_ELEMENTS = {
      "p", "pPr", "pStyle", "r", "rPr", "t", "br", ...
  }
  ```

**Type Checking:**
- All public function signatures use type hints
- Internal helpers use hints where complexity warrants (not for obvious cases like `for elem in body`)
- Use `str | None` syntax (Python 3.10+) for optional types, not `Optional[str]`

## Pydantic Models

**Location:** `src/models.py` — single file for all request/response models

**Naming:**
- Request classes: `ExtractStructureRequest`, `ValidateLocationsRequest`
- Response classes: `CompactStructureResponse`, `VerificationReport`
- Data classes: `LocationSnippet`, `AnswerPayload`, `ExpectedAnswer`, `ContentResult`
- Enums: `FileType`, `AnswerType`, `InsertionMode`, `LocationStatus`, `ContentStatus`

**Patterns:**
- All models inherit from `BaseModel`
- Use Enum for constrained strings: `FileType(str, Enum)`
- Optional fields have defaults: `current_value: str | None = None`
- Complex nested structures use sub-models: `VerificationReport` contains `VerificationSummary`

**Example from `models.py`:**
```python
class CompactStructureResponse(BaseModel):
    """Compact indexed representation of document structure."""
    compact_text: str
    id_to_xpath: dict[str, str]
    complex_elements: list[str]
```

## Dependency Flow

**Clean separation by layer:**
1. `models.py` — Pydantic data classes (no imports from handlers)
2. XML utilities (`xml_snippet_matching.py`, `xml_formatting.py`, `xml_validation.py`) — pure XML logic (imports only models, stdlib, lxml)
3. Format handlers (`word.py`, `excel.py`, `pdf.py`) — orchestrate handlers (import models, xml_utils)
4. Format-specific modules (`word_indexer.py`, `excel_verifier.py`, etc.) — detail work (import models, xml_utils, sometimes parent handler)
5. Test files — test any module

**No circular imports.**
- Handlers never import from server.py
- Submodules never import from parent handler module (word_indexer doesn't import word.py)

## Documentation in Code

**Module docstrings (required):**
Every `.py` file starts with a docstring explaining:
- What the module does
- What modules depend on it (if not obvious)
- Example from `word_element_analysis.py`:
  ```python
  """Word element analysis — text extraction, formatting hints, complexity detection.

  Helpers used by word_indexer.py to analyse individual OOXML elements and
  produce compact representations. Separated to keep word_indexer focused on
  tree walking and ID assignment.
  """
  ```

**Function docstrings (required for public):**
- One-liner or multi-line depending on complexity
- Include parameter types (though type hints do this)
- Include return type
- Include context for when to call it
- Example from `word_parser.py`:
  ```python
  def read_document_xml(file_bytes: bytes) -> bytes:
      """Extract word/document.xml from a .docx ZIP archive."""
  ```

**Inline comments (use sparingly):**
- Explain WHY, not WHAT
- Flag surprising implementations: `# Secure parser — disables external entities (XXE prevention)`
- Note when compensating for library quirks: `# openpyxl returns None for unset cells, convert to string`

## Copyright & License

**Required header on all source files:**
```python
# Copyright (C) 2025 the contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
```

---

*Convention analysis: 2025-02-16*
