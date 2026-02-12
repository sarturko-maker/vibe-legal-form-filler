"""Tests for the PDF (.pdf) handler."""

from pathlib import Path

import pytest

from src.handlers.pdf import (
    extract_structure,
    list_form_fields,
    validate_locations,
    write_answers,
)
from src.handlers.pdf_indexer import extract_structure_compact
from src.handlers.pdf_verifier import verify_output
from src.models import (
    AnswerPayload,
    Confidence,
    ContentStatus,
    ExpectedAnswer,
    InsertionMode,
    LocationSnippet,
    LocationStatus,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_pdf() -> bytes:
    return (FIXTURES / "simple_form.pdf").read_bytes()


@pytest.fixture
def multi_page_pdf() -> bytes:
    return (FIXTURES / "multi_page_form.pdf").read_bytes()


@pytest.fixture
def prefilled_pdf() -> bytes:
    return (FIXTURES / "prefilled_form.pdf").read_bytes()


# ── extract_structure_compact ────────────────────────────────────────────────


class TestExtractStructureCompact:
    def test_header_shows_field_count(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert "5 fields across 1 page" in result.compact_text

    def test_contains_field_ids(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert "[F1]" in result.compact_text
        assert "[F5]" in result.compact_text

    def test_contains_field_names(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert '"full_name"' in result.compact_text
        assert '"email"' in result.compact_text
        assert '"department"' in result.compact_text

    def test_shows_field_types(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert "(text)" in result.compact_text
        assert "(checkbox)" in result.compact_text
        assert "(dropdown" in result.compact_text

    def test_shows_dropdown_options(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert "options: HR | Engineering | Sales | Finance" in result.compact_text

    def test_empty_fields_marked_empty(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert "— empty" in result.compact_text
        assert "— unchecked" in result.compact_text

    def test_prefilled_shows_values(self, prefilled_pdf: bytes) -> None:
        result = extract_structure_compact(prefilled_pdf)
        assert '"Jane Smith"' in result.compact_text
        assert "— checked" in result.compact_text
        assert '"Engineering"' in result.compact_text

    def test_multi_page_shows_pages(self, multi_page_pdf: bytes) -> None:
        result = extract_structure_compact(multi_page_pdf)
        assert "8 fields across 3 pages" in result.compact_text
        assert "Page 1:" in result.compact_text
        assert "Page 2:" in result.compact_text
        assert "Page 3:" in result.compact_text

    def test_id_to_xpath_maps_to_native_names(
        self, simple_pdf: bytes
    ) -> None:
        result = extract_structure_compact(simple_pdf)
        assert result.id_to_xpath["F1"] == "full_name"
        assert result.id_to_xpath["F4"] == "agree_terms"
        assert result.id_to_xpath["F5"] == "department"

    def test_complex_elements_empty(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert result.complex_elements == []

    def test_nearby_text_context(self, simple_pdf: bytes) -> None:
        result = extract_structure_compact(simple_pdf)
        assert "Context:" in result.compact_text


class TestExtractStructureCompactNonAcroForm:
    def test_flat_pdf_returns_no_fields_message(self) -> None:
        """A PDF without form widgets should return a clear message."""
        import fitz
        doc = fitz.open()
        doc.new_page()
        flat_bytes = doc.tobytes()
        doc.close()

        result = extract_structure_compact(flat_bytes)
        assert "No fillable form fields found" in result.compact_text
        assert result.id_to_xpath == {}


# ── extract_structure ────────────────────────────────────────────────────────


class TestExtractStructure:
    def test_returns_field_list(self, simple_pdf: bytes) -> None:
        result = extract_structure(simple_pdf)
        assert result.fields is not None
        assert len(result.fields) == 5

    def test_field_ids(self, simple_pdf: bytes) -> None:
        result = extract_structure(simple_pdf)
        ids = [f.field_id for f in result.fields]
        assert ids == ["F1", "F2", "F3", "F4", "F5"]

    def test_field_labels_are_native_names(self, simple_pdf: bytes) -> None:
        result = extract_structure(simple_pdf)
        labels = [f.label for f in result.fields]
        assert "full_name" in labels
        assert "department" in labels

    def test_field_types(self, simple_pdf: bytes) -> None:
        result = extract_structure(simple_pdf)
        types = {f.field_id: f.field_type for f in result.fields}
        assert types["F1"] == "text"
        assert types["F4"] == "checkbox"
        assert types["F5"] == "dropdown"


# ── validate_locations ───────────────────────────────────────────────────────


class TestValidateLocations:
    def test_valid_field_ids_matched(self, simple_pdf: bytes) -> None:
        locs = [
            LocationSnippet(pair_id="q1", snippet="F1"),
            LocationSnippet(pair_id="q2", snippet="F5"),
        ]
        results = validate_locations(simple_pdf, locs)
        assert all(r.status == LocationStatus.MATCHED for r in results)

    def test_invalid_field_id_not_found(self, simple_pdf: bytes) -> None:
        locs = [LocationSnippet(pair_id="bad", snippet="F99")]
        results = validate_locations(simple_pdf, locs)
        assert results[0].status == LocationStatus.NOT_FOUND

    def test_matched_returns_context(self, simple_pdf: bytes) -> None:
        locs = [LocationSnippet(pair_id="q1", snippet="F1")]
        results = validate_locations(simple_pdf, locs)
        assert results[0].context == "full_name (text)"

    def test_matched_returns_field_id_as_xpath(
        self, simple_pdf: bytes
    ) -> None:
        locs = [LocationSnippet(pair_id="q1", snippet="F1")]
        results = validate_locations(simple_pdf, locs)
        assert results[0].xpath == "F1"

    def test_multi_page_field_ids(self, multi_page_pdf: bytes) -> None:
        locs = [
            LocationSnippet(pair_id="q1", snippet="F1"),
            LocationSnippet(pair_id="q6", snippet="F6"),
            LocationSnippet(pair_id="q8", snippet="F8"),
        ]
        results = validate_locations(multi_page_pdf, locs)
        assert all(r.status == LocationStatus.MATCHED for r in results)


# ── write_answers ────────────────────────────────────────────────────────────


class TestWriteAnswers:
    def test_write_text_field(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(
                pair_id="q1", xpath="F1",
                insertion_xml="John Doe",
                mode=InsertionMode.REPLACE_CONTENT,
            ),
        ]
        filled = write_answers(simple_pdf, answers)
        result = extract_structure_compact(filled)
        assert '"John Doe"' in result.compact_text

    def test_write_checkbox(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(
                pair_id="q1", xpath="F4",
                insertion_xml="yes",
                mode=InsertionMode.REPLACE_CONTENT,
            ),
        ]
        filled = write_answers(simple_pdf, answers)
        result = extract_structure_compact(filled)
        assert "— checked" in result.compact_text

    def test_write_dropdown(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(
                pair_id="q1", xpath="F5",
                insertion_xml="Sales",
                mode=InsertionMode.REPLACE_CONTENT,
            ),
        ]
        filled = write_answers(simple_pdf, answers)
        result = extract_structure_compact(filled)
        assert '"Sales"' in result.compact_text

    def test_write_multiple_fields(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(pair_id="q1", xpath="F1",
                          insertion_xml="Alice", mode=InsertionMode.REPLACE_CONTENT),
            AnswerPayload(pair_id="q2", xpath="F2",
                          insertion_xml="alice@test.com", mode=InsertionMode.REPLACE_CONTENT),
            AnswerPayload(pair_id="q3", xpath="F5",
                          insertion_xml="HR", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(simple_pdf, answers)
        result = extract_structure_compact(filled)
        assert '"Alice"' in result.compact_text
        assert '"alice@test.com"' in result.compact_text
        assert '"HR"' in result.compact_text

    def test_unknown_field_id_skipped(self, simple_pdf: bytes) -> None:
        """Writing to a nonexistent field ID should not crash."""
        answers = [
            AnswerPayload(pair_id="q1", xpath="F99",
                          insertion_xml="value", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(simple_pdf, answers)
        assert len(filled) > 0

    def test_preserves_existing_fields(self, prefilled_pdf: bytes) -> None:
        answers = [
            AnswerPayload(pair_id="q1", xpath="F3",
                          insertion_xml="1990-01-15", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(prefilled_pdf, answers)
        result = extract_structure_compact(filled)
        assert '"Jane Smith"' in result.compact_text
        assert '"1990-01-15"' in result.compact_text


# ── verify_output ────────────────────────────────────────────────────────────


class TestVerifyOutput:
    def test_all_matched(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(pair_id="q1", xpath="F1",
                          insertion_xml="Test Name", mode=InsertionMode.REPLACE_CONTENT),
            AnswerPayload(pair_id="q2", xpath="F2",
                          insertion_xml="test@test.com", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(simple_pdf, answers)

        expected = [
            ExpectedAnswer(pair_id="q1", xpath="F1", expected_text="Test Name"),
            ExpectedAnswer(pair_id="q2", xpath="F2", expected_text="test@test.com"),
        ]
        report = verify_output(filled, expected)
        assert report.summary.total == 2
        assert report.summary.matched == 2
        assert report.summary.mismatched == 0

    def test_mismatched_text(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(pair_id="q1", xpath="F1",
                          insertion_xml="Actual", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(simple_pdf, answers)

        expected = [
            ExpectedAnswer(pair_id="q1", xpath="F1", expected_text="Wrong"),
        ]
        report = verify_output(filled, expected)
        assert report.summary.mismatched == 1

    def test_missing_field_id(self, simple_pdf: bytes) -> None:
        expected = [
            ExpectedAnswer(pair_id="bad", xpath="F99", expected_text="X"),
        ]
        report = verify_output(simple_pdf, expected)
        assert report.summary.missing == 1

    def test_case_insensitive_match(self, simple_pdf: bytes) -> None:
        answers = [
            AnswerPayload(pair_id="q1", xpath="F1",
                          insertion_xml="Net-Zero Target", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(simple_pdf, answers)

        expected = [
            ExpectedAnswer(pair_id="q1", xpath="F1",
                           expected_text="net-zero target"),
        ]
        report = verify_output(filled, expected)
        assert report.summary.matched == 1
        assert report.summary.mismatched == 0

    def test_no_structural_issues(self, simple_pdf: bytes) -> None:
        report = verify_output(simple_pdf, [])
        assert report.structural_issues == []
        assert report.summary.structural_issues == 0

    def test_confidence_tracking(self, simple_pdf: bytes) -> None:
        expected = [
            ExpectedAnswer(pair_id="q1", xpath="F1", expected_text="",
                           confidence=Confidence.KNOWN),
            ExpectedAnswer(pair_id="q2", xpath="F2", expected_text="",
                           confidence=Confidence.UNCERTAIN),
            ExpectedAnswer(pair_id="q3", xpath="F3", expected_text="",
                           confidence=Confidence.UNKNOWN),
        ]
        report = verify_output(simple_pdf, expected)
        assert report.summary.confidence_known == 1
        assert report.summary.confidence_uncertain == 1
        assert report.summary.confidence_unknown == 1
        assert "manual review needed" in report.summary.confidence_note


# ── list_form_fields ─────────────────────────────────────────────────────────


class TestListFormFields:
    def test_returns_all_fields(self, simple_pdf: bytes) -> None:
        fields = list_form_fields(simple_pdf)
        assert len(fields) == 5

    def test_field_ids_sequential(self, simple_pdf: bytes) -> None:
        fields = list_form_fields(simple_pdf)
        ids = [f.field_id for f in fields]
        assert ids == ["F1", "F2", "F3", "F4", "F5"]

    def test_field_types(self, simple_pdf: bytes) -> None:
        fields = list_form_fields(simple_pdf)
        type_map = {f.field_id: f.field_type for f in fields}
        assert type_map["F1"] == "text"
        assert type_map["F4"] == "checkbox"
        assert type_map["F5"] == "dropdown"

    def test_prefilled_current_values(self, prefilled_pdf: bytes) -> None:
        fields = list_form_fields(prefilled_pdf)
        value_map = {f.field_id: f.current_value for f in fields}
        assert value_map["F1"] == "Jane Smith"
        assert value_map["F2"] == "jane@example.com"
        assert value_map["F3"] is None  # empty


# ── Full Pipeline ────────────────────────────────────────────────────────────


class TestFullPipeline:
    def test_extract_validate_write_verify(self, simple_pdf: bytes) -> None:
        """End-to-end: extract → validate → write → verify."""
        # Step 1: Extract
        compact = extract_structure_compact(simple_pdf)
        assert "[F1]" in compact.compact_text

        # Step 2: Validate
        field_ids = ["F1", "F2", "F3", "F4", "F5"]
        locs = [
            LocationSnippet(pair_id=f"q{i}", snippet=fid)
            for i, fid in enumerate(field_ids, 1)
        ]
        validated = validate_locations(simple_pdf, locs)
        assert all(v.status == LocationStatus.MATCHED for v in validated)

        # Step 3: Write
        values = [
            "Alice Wonderland", "alice@test.com", "2000-01-01", "true", "Finance",
        ]
        payloads = [
            AnswerPayload(
                pair_id=f"q{i}", xpath=fid,
                insertion_xml=val, mode=InsertionMode.REPLACE_CONTENT,
            )
            for i, (fid, val) in enumerate(zip(field_ids, values), 1)
        ]
        filled = write_answers(simple_pdf, payloads)

        # Step 4: Verify (checkbox stores "Yes" not "true")
        verify_values = [
            "Alice Wonderland", "alice@test.com", "2000-01-01", "Yes", "Finance",
        ]
        expected = [
            ExpectedAnswer(pair_id=f"q{i}", xpath=fid, expected_text=val)
            for i, (fid, val) in enumerate(zip(field_ids, verify_values), 1)
        ]
        report = verify_output(filled, expected)
        assert report.summary.total == 5
        assert report.summary.matched == 5
        assert report.summary.mismatched == 0
        assert report.summary.missing == 0

    def test_multi_page_pipeline(self, multi_page_pdf: bytes) -> None:
        """End-to-end across 3 pages."""
        compact = extract_structure_compact(multi_page_pdf)
        assert "Page 1:" in compact.compact_text
        assert "Page 3:" in compact.compact_text

        answers = [
            AnswerPayload(pair_id="q1", xpath="F1",
                          insertion_xml="Bob", mode=InsertionMode.REPLACE_CONTENT),
            AnswerPayload(pair_id="q7", xpath="F7",
                          insertion_xml="Bob Signature", mode=InsertionMode.REPLACE_CONTENT),
        ]
        filled = write_answers(multi_page_pdf, answers)

        expected = [
            ExpectedAnswer(pair_id="q1", xpath="F1", expected_text="Bob"),
            ExpectedAnswer(pair_id="q7", xpath="F7",
                           expected_text="Bob Signature"),
        ]
        report = verify_output(filled, expected)
        assert report.summary.matched == 2
