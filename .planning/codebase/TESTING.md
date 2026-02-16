# Testing Patterns

**Analysis Date:** 2025-02-16

## Test Framework

**Runner:**
- pytest 9.0.2
- Config: `pyproject.toml` with `[tool.pytest.ini_options] testpaths = ["tests"]`

**Assertion Library:**
- Python's built-in `assert` statements (no extra assertion library)

**Run Commands:**
```bash
pytest                          # Run all tests (207 tests across 13 files)
pytest tests/test_word.py       # Run single test file
pytest tests/test_word.py::TestExtractStructure::test_returns_body_xml  # Single test
pytest -v                       # Verbose output
pytest --collect-only           # List all tests without running
```

**Test Count:**
- 207 total tests (13 test files)
- No separate coverage tool; tests validate critical paths

## Test File Organization

**Location:**
- Mirror source structure: `src/handlers/word.py` → `tests/test_word.py`
- One test file per public module
- Location: `tests/` directory at project root

**Test Files:**
- `tests/test_word.py` — Word handler tests (70+ tests)
- `tests/test_excel.py` — Excel handler tests (50+ tests)
- `tests/test_pdf.py` — PDF handler tests (40+ tests)
- `tests/test_word_verifier.py` — Word verification tests (20+ tests)
- `tests/test_xml_utils.py` — XML utility tests (15+ tests)
- `tests/test_e2e_integration.py` — Full pipeline tests (25+ tests)
- `tests/test_file_path.py` — Input validation tests
- `tests/fixtures/` — Test document files (sample .docx, .xlsx, .pdf)

**Naming:**
- Test files: `test_<module_being_tested>.py`
- Test classes: `Test<FunctionName>` or `Test<ScenarioName>`
- Test functions: `test_<scenario_description>` (descriptive, not abbreviated)

## Test Structure

**Class-based organization:**
- Group related tests into classes
- One class per function or feature area
- Classes don't inherit; used for logical grouping only

**Pattern from `test_word.py`:**
```python
class TestExtractStructure:
    def test_returns_body_xml(self, table_docx: bytes) -> None:
        result = extract_structure(table_docx)
        assert result.body_xml is not None
        assert "<w:body" in result.body_xml

    def test_body_xml_is_parseable(self, table_docx: bytes) -> None:
        result = extract_structure(table_docx)
        root = etree.fromstring(result.body_xml.encode("utf-8"))
        assert root.tag == f"{{{W}}}body"

class TestValidateLocations:
    def test_matches_existing_paragraph(self, table_docx: bytes) -> None:
        # Detailed test...
```

**Fixtures (pytest pattern):**
- Defined with `@pytest.fixture` decorator
- Located at top of test file or in `conftest.py`
- Return test data (loaded document bytes)
- Example from `test_word.py`:
  ```python
  @pytest.fixture
  def table_docx() -> bytes:
      return (FIXTURES / "table_questionnaire.docx").read_bytes()

  @pytest.fixture
  def placeholder_docx() -> bytes:
      return (FIXTURES / "placeholder_form.docx").read_bytes()
  ```

**Fixture dependencies:**
- Can depend on other fixtures
- Example from `test_word_verifier.py`:
  ```python
  @pytest.fixture
  def filled_docx(table_docx: bytes) -> bytes:
      """A table_questionnaire.docx with two answers written into it."""
      answers = [
          AnswerPayload(pair_id="q1", xpath="./w:tbl[1]/w:tr[2]/w:tc[2]", ...),
          AnswerPayload(pair_id="q2", xpath="./w:tbl[1]/w:tr[3]/w:tc[2]", ...),
      ]
      return write_answers(table_docx, answers)
  ```

## Test Patterns

**Arrange-Act-Assert:**
All tests follow this structure:

```python
def test_extract_returns_compact_text(self, table_docx: bytes) -> None:
    # Arrange (via fixture)

    # Act
    result = extract_structure_compact(table_docx)

    # Assert
    assert result.compact_text is not None
    assert "P1:" in result.compact_text
    assert "T1-R1-C1:" in result.compact_text
```

**Setup & Teardown:**
- No setup/teardown needed for most tests (stateless operations)
- Use fixtures instead of setUp/tearDown methods
- File cleanup handled automatically by pytest

**Test isolation:**
- Each test is independent
- No shared state between tests
- Fixtures create fresh copies of test data

**Example from `test_excel.py` (complete test):**
```python
def test_contains_cell_ids(self, vendor_xlsx: bytes) -> None:
    result = extract_structure_compact(vendor_xlsx)
    assert "S1-R1-C1:" in result.compact_text
    assert "S1-R2-C1:" in result.compact_text
    assert "S2-R1-C1:" in result.compact_text
```

## Mocking & External Dependencies

**Pattern:**
- Minimal mocking; prefer real documents
- Use fixture documents instead of mocking lxml/openpyxl/fitz
- No HTTP mocks (no network calls made)
- No database mocks (no database used)

**Test fixtures (real files):**
- `tests/fixtures/table_questionnaire.docx` — two-column Q&A table (Word)
- `tests/fixtures/placeholder_form.docx` — paragraphs with "[Enter here]" placeholders (Word)
- `tests/fixtures/vendor_assessment.xlsx` — multi-sheet form (Excel)
- `tests/fixtures/simple_form.pdf` — text fields, checkbox, dropdown (PDF)
- `tests/fixtures/multi_page_form.pdf` — fields across 3 pages (PDF)
- `tests/fixtures/prefilled_form.pdf` — some fields pre-filled (PDF)

**When to mock:**
- Only for testing error paths (e.g., corrupt ZIP file) — create minimal malformed bytes on the fly
- Example from `test_word.py`:
  ```python
  def test_invalid_bytes_raises(self) -> None:
      with pytest.raises(Exception):
          extract_structure(b"not a docx file")
  ```

**No mocking of:**
- lxml, openpyxl, or PyMuPDF (test with real implementations)
- File system (use real fixture files)
- Document parsing (always test against real documents)

## Test Data

**Fixture location:**
- `tests/fixtures/` directory
- Sample documents committed to repo (not generated)
- Files: `.docx`, `.xlsx`, `.pdf` (binary files)

**Creating new fixtures:**
- Create real documents in Word/Excel/Acrobat
- Save to `tests/fixtures/`
- Reference in test as: `FIXTURES / "document_name.docx"`

**Fixture loading pattern:**
```python
FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def my_docx() -> bytes:
    return (FIXTURES / "my_document.docx").read_bytes()
```

## Test Categories

**Unit Tests (extract, validate, write):**
- Test individual handler functions in isolation
- Each function has its own test class
- Example class: `TestExtractStructureCompact`, `TestValidateLocations`, `TestWriteAnswers`

**Verification Tests (verify_output):**
- Test post-write verification (structural + content checks)
- Separate test file: `tests/test_word_verifier.py`, `tests/test_excel_verifier.py`, etc.
- Example: `test_all_matched()`, `test_one_mismatched()`, `test_structural_issue_bare_run()`

**Integration Tests (full pipeline):**
- Test extract → validate → write → verify flow end-to-end
- Located in: `tests/test_e2e_integration.py`
- Classes: `TestWordPipeline`, `TestExcelPipeline`, `TestPdfPipeline`
- Example test name: `test_full_pipeline_inline_and_file()`

**Edge Case & Adversarial Tests:**
- Corrupt files, malformed input, path traversal attempts
- Located in: `tests/test_e2e_integration.py::TestAdversarialInputs`
- Examples:
  - `test_path_traversal_passwd()` — prevent reading `/etc/passwd`
  - `test_wrong_format_xlsx_as_word()` — reject Excel as Word
  - `test_malformed_answers_json()` — reject invalid JSON
  - `test_xml_injection_in_answer()` — reject dangerous XML

## Common Test Patterns

**Test multiple status outcomes:**
```python
class TestValidateLocations:
    def test_matches_existing_paragraph(self, table_docx: bytes) -> None:
        # Test successful match
        locations = [LocationSnippet(pair_id="q1", snippet=snippet_xml)]
        validated = validate_locations(table_docx, locations)
        assert validated[0].status == LocationStatus.MATCHED

    def test_not_found(self, table_docx: bytes) -> None:
        # Test no match
        fake_snippet = "<w:p>...</w:p>"
        locations = [LocationSnippet(pair_id="q2", snippet=fake_snippet)]
        validated = validate_locations(table_docx, locations)
        assert validated[0].status == LocationStatus.NOT_FOUND

    def test_ambiguous_match(self, table_docx: bytes) -> None:
        # Test multiple matches
        locations = [LocationSnippet(pair_id="q3", snippet=duplicate_text)]
        validated = validate_locations(table_docx, locations)
        assert validated[0].status == LocationStatus.AMBIGUOUS
```

**Test content verification:**
```python
class TestVerifyOutputContentMismatched:
    def test_one_mismatched(self, filled_docx: bytes) -> None:
        expected = [
            ExpectedAnswer(
                pair_id="q1", xpath="./w:tbl[1]/w:tr[2]/w:tc[2]",
                expected_text="Acme Corp",
            ),
        ]
        report = verify_output(filled_docx, expected)
        assert report.summary.mismatched == 1
        assert report.content_results[0].status == ContentStatus.MISMATCHED
        assert "Acme Corporation" in report.content_results[0].actual
```

**Test error handling:**
```python
def test_invalid_cell_id_returns_missing(self, vendor_xlsx: bytes) -> None:
    expected = [
        ExpectedAnswer(
            pair_id="q1", xpath="S1-R2-Z5",  # Z invalid
            expected_text="test",
        ),
    ]
    report = verify_output(vendor_xlsx, expected)
    assert report.summary.missing == 1
```

**Test XML parsing/building:**
```python
class TestFindSnippetInBody:
    def test_finds_exact_match(self) -> None:
        para = _make_paragraph("Hello")
        body = _make_body(para)
        snippet = f'<w:p xmlns:w="{W}"><w:r>...<w:t>Hello</w:t></w:r></w:p>'
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 1

    def test_snippet_without_namespace_decl(self) -> None:
        """Snippet that uses w: prefix but doesn't declare namespace."""
        para = _make_paragraph("Test")
        body = _make_body(para)
        snippet = "<w:p><w:r>...<w:t>Test</w:t></w:r></w:p>"
        matches = find_snippet_in_body(body, snippet)
        assert len(matches) == 1
```

## Test Documentation

**Test names describe the scenario:**
- ✓ `test_extract_structure_returns_body_xml_for_valid_docx()`
- ✓ `test_validate_locations_matches_existing_snippet_with_whitespace_variance()`
- ✓ `test_write_answers_raises_on_invalid_cell_id()`
- ✗ `test_extract()` (too vague)
- ✗ `test_1()` (not descriptive)

**Docstrings on complex tests:**
```python
def test_snippet_without_namespace_decl(self) -> None:
    """Snippet that uses w: prefix but doesn't declare the namespace.

    Validates that snippet matching is forgiving about namespace declarations.
    """
    para = _make_paragraph("Test")
    # ...
```

**Comments only for setup complexity:**
```python
def test_validate_locations_with_multiple_matches(self, table_docx: bytes) -> None:
    # Extract a snippet from the actual document and use it twice (ambiguous)
    result = extract_structure(table_docx)
    body = etree.fromstring(result.body_xml.encode("utf-8"))
    first_para = body.find(".//w:p", NAMESPACES)
    snippet_xml = etree.tostring(first_para, encoding="unicode")

    # Now write the same snippet twice to create duplication
    locations = [
        LocationSnippet(pair_id="q1", snippet=snippet_xml),
        LocationSnippet(pair_id="q2", snippet=snippet_xml),
    ]
    validated = validate_locations(table_docx, locations)

    assert validated[0].status == LocationStatus.AMBIGUOUS
    assert validated[1].status == LocationStatus.AMBIGUOUS
```

## Running Tests

**Full suite:**
```bash
pytest                  # All 207 tests, ~15 seconds
```

**By category:**
```bash
pytest tests/test_word.py                   # Word handler only
pytest tests/test_e2e_integration.py        # Pipeline tests only
pytest tests/test_e2e_integration.py::TestAdversarialInputs  # Adversarial tests
```

**By test name pattern:**
```bash
pytest -k "extract_compact"     # All tests with "extract_compact"
pytest -k "verify"              # All verification tests
pytest -k "not adversarial"     # All tests except adversarial
```

**Verbose:**
```bash
pytest -v                       # Show test names as they run
pytest -v --tb=short           # Show test names + short tracebacks
```

**Failed tests only:**
```bash
pytest --lf                    # Run last failed
pytest --ff                    # Run failed first, then rest
```

## Test Reliability

**Deterministic:**
- All tests produce same result every run (no randomness, no timing)
- Fixture documents are fixed (not generated)
- No flaky tests (no timeouts, no concurrency issues)

**Fast:**
- Individual tests: <100ms
- Full suite: ~15 seconds
- No sleep() calls in tests

**Isolated:**
- Each test independent
- No state shared between tests
- Fixture cleanup automatic

## Continuous Integration

**Not configured in this repo.**
- Tests are local only
- Run before committing: `pytest`
- All tests must pass before commit

## Code Coverage

**Not enforced.**
- No coverage targets or minimum percentages
- Critical paths covered by integration tests (`test_e2e_integration.py`)
- Edge cases covered by adversarial tests

## Future Test Files

**When adding new functionality:**

1. **New handler format** (e.g., CSV):
   - Create `src/handlers/csv.py` and submodules
   - Create `tests/test_csv.py` with same structure as `test_word.py`
   - Add fixtures to `tests/fixtures/` (sample CSV file)
   - Add pipeline tests to `tests/test_e2e_integration.py::TestCsvPipeline`

2. **New public function in existing handler**:
   - Add tests to existing handler test file
   - Create new test class in same file
   - Example: `tests/test_word.py::TestNewFeature`

3. **New xml_utils function**:
   - Add tests to `tests/test_xml_utils.py`
   - Follow existing pattern in that file

---

*Testing analysis: 2025-02-16*
