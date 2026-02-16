# Copyright (C) 2025 the contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Transport parity tests for all 6 core MCP tools.

Each test calls a tool over HTTP (via mcp_session) and directly (importing
the function), then asserts the results are identical. This proves the HTTP
transport does not alter tool outputs.
"""

from tests.conftest import call_tool, parse_tool_result
from src.tools_extract import (
    build_insertion_xml,
    extract_structure,
    extract_structure_compact,
    validate_locations,
)
from src.tools_write import verify_output, write_answers

FIXTURE = "tests/fixtures/table_questionnaire.docx"

# Minimal OOXML context for build_insertion_xml
_CONTEXT_XML = (
    '<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:r><w:rPr>"
    '<w:rFonts w:ascii="Calibri"/><w:sz w:val="22"/>'
    "</w:rPr><w:t>placeholder</w:t></w:r></w:p>"
)


def test_extract_structure_compact_parity(mcp_session):
    """HTTP and direct extract_structure_compact return identical JSON."""
    client, headers = mcp_session
    args = {"file_path": FIXTURE}

    resp = call_tool(client, headers, "extract_structure_compact", args)
    http_result = parse_tool_result(resp)

    direct = extract_structure_compact(file_path=FIXTURE)

    assert http_result == direct


def test_extract_structure_parity(mcp_session):
    """HTTP and direct extract_structure return identical JSON."""
    client, headers = mcp_session
    args = {"file_path": FIXTURE}

    resp = call_tool(client, headers, "extract_structure", args)
    http_result = parse_tool_result(resp)

    direct = extract_structure(file_path=FIXTURE)

    assert http_result == direct


def test_validate_locations_parity(mcp_session):
    """HTTP and direct validate_locations return identical JSON."""
    client, headers = mcp_session

    compact = extract_structure_compact(file_path=FIXTURE)
    ids = list(compact["id_to_xpath"].keys())
    id1, id2 = ids[4], ids[5]
    locations = [
        {"pair_id": "q1", "snippet": id1},
        {"pair_id": "q2", "snippet": id2},
    ]
    args = {"file_path": FIXTURE, "locations": locations}

    resp = call_tool(client, headers, "validate_locations", args)
    http_result = parse_tool_result(resp)

    direct = validate_locations(file_path=FIXTURE, locations=locations)

    assert http_result == direct


def test_build_insertion_xml_parity(mcp_session):
    """HTTP and direct build_insertion_xml return identical JSON."""
    client, headers = mcp_session
    args = {
        "answer_text": "Test Answer",
        "target_context_xml": _CONTEXT_XML,
        "answer_type": "plain_text",
    }

    resp = call_tool(client, headers, "build_insertion_xml", args)
    http_result = parse_tool_result(resp)

    direct = build_insertion_xml(
        answer_text="Test Answer",
        target_context_xml=_CONTEXT_XML,
        answer_type="plain_text",
    )

    assert http_result == direct


def test_write_answers_parity(mcp_session, tmp_path):
    """HTTP and direct write_answers produce identical output files."""
    client, headers = mcp_session

    compact = extract_structure_compact(file_path=FIXTURE)
    xpath = compact["id_to_xpath"]["T1-R2-C2"]
    xml_result = build_insertion_xml(
        answer_text="Acme Corp",
        target_context_xml=_CONTEXT_XML,
        answer_type="plain_text",
    )
    answer = {
        "pair_id": "q1",
        "xpath": xpath,
        "insertion_xml": xml_result["insertion_xml"],
        "mode": "replace_content",
    }

    http_out = str(tmp_path / "http_filled.docx")
    direct_out = str(tmp_path / "direct_filled.docx")

    http_args = {
        "file_path": FIXTURE,
        "answers": [answer],
        "output_file_path": http_out,
    }
    resp = call_tool(client, headers, "write_answers", http_args)
    http_result = parse_tool_result(resp)

    direct_result = write_answers(
        file_path=FIXTURE,
        answers=[answer],
        output_file_path=direct_out,
    )

    assert http_result["file_path"] is not None
    assert direct_result["file_path"] is not None

    http_bytes = (tmp_path / "http_filled.docx").read_bytes()
    direct_bytes = (tmp_path / "direct_filled.docx").read_bytes()
    assert http_bytes == direct_bytes


def test_verify_output_parity(mcp_session):
    """HTTP and direct verify_output return identical JSON."""
    client, headers = mcp_session

    compact = extract_structure_compact(file_path=FIXTURE)
    xpath = compact["id_to_xpath"]["T1-R2-C1"]
    expected_answers = [
        {"pair_id": "q1", "xpath": xpath, "expected_text": "legal name"},
    ]
    args = {"file_path": FIXTURE, "expected_answers": expected_answers}

    resp = call_tool(client, headers, "verify_output", args)
    http_result = parse_tool_result(resp)

    direct = verify_output(file_path=FIXTURE, expected_answers=expected_answers)

    assert http_result == direct
