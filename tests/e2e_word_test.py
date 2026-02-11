"""End-to-end test: fill two Word documents through the full pipeline.

Runs the complete flow for each fixture:
  extract_structure → validate_locations → build_insertion_xml → write_answers

Produces filled .docx files in tests/outputs/ for manual inspection in Word.
No assertions — this script just produces documents.

Usage:
    python -m tests.e2e_word_test
"""

from __future__ import annotations

from pathlib import Path

from src.handlers.word import (
    build_insertion_xml,
    extract_structure,
    validate_locations,
    write_answers,
)
from src.models import (
    AnswerPayload,
    AnswerType,
    BuildInsertionXmlRequest,
    InsertionMode,
    LocationSnippet,
    LocationStatus,
)

FIXTURES = Path(__file__).parent / "fixtures"
OUTPUTS = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)


# ── Table questionnaire ─────────────────────────────────────────────────────


def fill_table_questionnaire() -> None:
    """Fill the table_questionnaire.docx with realistic corporate answers."""
    print("=== Table Questionnaire ===")
    file_bytes = (FIXTURES / "table_questionnaire.docx").read_bytes()

    # Step 1: Extract structure
    structure = extract_structure(file_bytes)
    print(f"  Extracted body XML ({len(structure.body_xml)} chars)")

    # Step 2: Define question/location pairs using OOXML snippets from the fixture.
    # These are the question cell paragraphs — each is unique so they match exactly.
    question_pairs = [
        {
            "pair_id": "q1_legal_name",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
                '<w:sz w:val="20"/>'
                "</w:rPr>"
                "<w:t>What is the full legal name of your company?</w:t>"
                "</w:r></w:p>"
            ),
            "answer": "Meridian Dynamics Corporation",
        },
        {
            "pair_id": "q2_address",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
                '<w:sz w:val="20"/>'
                "</w:rPr>"
                "<w:t>What is your company's principal address?</w:t>"
                "</w:r></w:p>"
            ),
            "answer": "1200 Innovation Drive, Suite 400, Austin, TX 78701",
        },
        {
            "pair_id": "q3_contact",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
                '<w:sz w:val="20"/>'
                "</w:rPr>"
                "<w:t>What is the name and title of the primary contact?</w:t>"
                "</w:r></w:p>"
            ),
            "answer": "Sarah Chen, General Counsel",
        },
        {
            "pair_id": "q4_cyber_insurance",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
                '<w:sz w:val="20"/>'
                "</w:rPr>"
                "<w:t>Does your company maintain cyber liability insurance?"
                " If so, state the coverage limit.</w:t>"
                "</w:r></w:p>"
            ),
            "answer": "Yes. Our cyber liability policy provides $10M aggregate coverage"
            " through Lloyd's of London, policy renewed annually.",
        },
    ]

    locations = [
        LocationSnippet(pair_id=qp["pair_id"], snippet=qp["snippet"])
        for qp in question_pairs
    ]
    validated = validate_locations(file_bytes, locations)

    for v in validated:
        print(f"  {v.pair_id}: {v.status.value}"
              f"{' → ' + v.xpath if v.xpath else ''}")

    # Step 3: Build insertion XML for each answer.
    # The question cell's formatting is used as the target context;
    # answers go into the adjacent answer cell (same row, next column).
    answers_to_write: list[AnswerPayload] = []

    for i, qp in enumerate(question_pairs):
        v = validated[i]
        if v.status != LocationStatus.MATCHED:
            print(f"  SKIP {qp['pair_id']}: {v.status.value}")
            continue

        # Build insertion XML inheriting formatting from the question cell
        build_resp = build_insertion_xml(BuildInsertionXmlRequest(
            answer_text=qp["answer"],
            target_context_xml=qp["snippet"],
            answer_type=AnswerType.PLAIN_TEXT,
        ))
        print(f"  Built XML for {qp['pair_id']}: valid={build_resp.valid}")

        # The question is in column 1; the answer goes in column 2 of the same row.
        # XPath pattern: question is at ./w:tbl[1]/w:tr[N]/w:tc[1]/w:p[1]
        # answer cell is at ./w:tbl[1]/w:tr[N]/w:tc[2]/w:p[1]
        answer_xpath = v.xpath.replace("/w:tc[1]/", "/w:tc[2]/")

        answers_to_write.append(AnswerPayload(
            pair_id=qp["pair_id"],
            xpath=answer_xpath,
            insertion_xml=build_resp.insertion_xml,
            mode=InsertionMode.REPLACE_CONTENT,
        ))

    # Step 4: Write all answers
    result_bytes = write_answers(file_bytes, answers_to_write)

    output_path = OUTPUTS / "table_questionnaire_FILLED.docx"
    output_path.write_bytes(result_bytes)
    print(f"  Wrote {output_path} ({len(result_bytes)} bytes)")


# ── Placeholder form ────────────────────────────────────────────────────────


def fill_placeholder_form() -> None:
    """Fill the placeholder_form.docx (NDA) with realistic party details."""
    print("\n=== Placeholder Form (NDA) ===")
    file_bytes = (FIXTURES / "placeholder_form.docx").read_bytes()

    # Step 1: Extract structure
    structure = extract_structure(file_bytes)
    print(f"  Extracted body XML ({len(structure.body_xml)} chars)")

    # Step 2: Define question/location pairs.
    # Some paragraphs are unique (date, party names, jurisdiction).
    # Address and Printed Name paragraphs are duplicated, so we use direct
    # XPaths for those instead of snippet matching.
    unique_pairs = [
        {
            "pair_id": "date",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:sz w:val="24"/>'
                "</w:rPr>"
                '<w:t xml:space="preserve">This Non-Disclosure Agreement'
                ' (the "Agreement") is entered into as of </w:t>'
                "</w:r><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:i/><w:sz w:val="24"/>'
                "</w:rPr>"
                "<w:t>[Enter date]</w:t>"
                "</w:r><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:sz w:val="24"/>'
                "</w:rPr>"
                '<w:t xml:space="preserve"> by and between:</w:t>'
                "</w:r></w:p>"
            ),
            "answer": "February 11, 2026",
        },
        {
            "pair_id": "party1_name",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:b/><w:sz w:val="24"/>'
                "</w:rPr>"
                '<w:t xml:space="preserve">'
                'Party 1 ("Disclosing Party"): '
                "</w:t></w:r><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:sz w:val="24"/>'
                "</w:rPr>"
                "<w:t>_______________</w:t>"
                "</w:r></w:p>"
            ),
            "answer": "Meridian Dynamics Corporation",
        },
        {
            "pair_id": "party2_name",
            "snippet": (
                "<w:p><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:b/><w:sz w:val="24"/>'
                "</w:rPr>"
                '<w:t xml:space="preserve">'
                'Party 2 ("Receiving Party"): '
                "</w:t></w:r><w:r><w:rPr>"
                '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                '<w:sz w:val="24"/>'
                "</w:rPr>"
                "<w:t>_______________</w:t>"
                "</w:r></w:p>"
            ),
            "answer": "Apex Consulting Group LLC",
        },
    ]

    locations = [
        LocationSnippet(pair_id=p["pair_id"], snippet=p["snippet"])
        for p in unique_pairs
    ]
    validated = validate_locations(file_bytes, locations)

    for v in validated:
        print(f"  {v.pair_id}: {v.status.value}"
              f"{' → ' + v.xpath if v.xpath else ''}")

    # Step 3: Build insertion XML and collect answer payloads.
    answers_to_write: list[AnswerPayload] = []

    for i, pair in enumerate(unique_pairs):
        v = validated[i]
        if v.status != LocationStatus.MATCHED:
            print(f"  SKIP {pair['pair_id']}: {v.status.value}")
            continue

        build_resp = build_insertion_xml(BuildInsertionXmlRequest(
            answer_text=pair["answer"],
            target_context_xml=pair["snippet"],
            answer_type=AnswerType.PLAIN_TEXT,
        ))
        print(f"  Built XML for {pair['pair_id']}: valid={build_resp.valid}")

        # Date uses REPLACE_PLACEHOLDER; party names use REPLACE_PLACEHOLDER too
        answers_to_write.append(AnswerPayload(
            pair_id=pair["pair_id"],
            xpath=v.xpath,
            insertion_xml=build_resp.insertion_xml,
            mode=InsertionMode.REPLACE_PLACEHOLDER,
        ))

    # For the ambiguous paragraphs (Address x2, Printed Name x2), use direct
    # XPaths. The body structure is: p[1]=title, p[2]=intro+date, p[3]=Party1,
    # p[4]=Address1, p[5]=Party2, p[6]=Address2, ...
    # p[13]=PrintedName1, p[15]=PrintedName2
    ambiguous_answers = [
        ("addr1", "./w:p[4]", "123 Innovation Drive, Austin, TX 78701"),
        ("addr2", "./w:p[6]", "456 Commerce Street, Floor 12, New York, NY 10005"),
        ("printed1", "./w:p[13]", "Sarah Chen"),
        ("printed2", "./w:p[15]", "James Whitfield"),
    ]

    target_context = (
        '<w:r><w:rPr>'
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
        '<w:sz w:val="24"/>'
        '</w:rPr><w:t>placeholder</w:t></w:r>'
    )

    for pair_id, xpath, answer_text in ambiguous_answers:
        build_resp = build_insertion_xml(BuildInsertionXmlRequest(
            answer_text=answer_text,
            target_context_xml=target_context,
            answer_type=AnswerType.PLAIN_TEXT,
        ))
        print(f"  Built XML for {pair_id} (direct xpath): valid={build_resp.valid}")

        answers_to_write.append(AnswerPayload(
            pair_id=pair_id,
            xpath=xpath,
            insertion_xml=build_resp.insertion_xml,
            mode=InsertionMode.REPLACE_PLACEHOLDER,
        ))

    # Step 4: Write all answers
    result_bytes = write_answers(file_bytes, answers_to_write)

    output_path = OUTPUTS / "placeholder_form_FILLED.docx"
    output_path.write_bytes(result_bytes)
    print(f"  Wrote {output_path} ({len(result_bytes)} bytes)")


# ── Main ────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    fill_table_questionnaire()
    fill_placeholder_form()
    print("\nDone. Open the files in tests/outputs/ to inspect results.")
