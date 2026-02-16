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

"""Concurrent request tests proving stateless design (TEST-05).

Spawns multiple threads making simultaneous tool calls and verifies that
all succeed without cross-contamination or interference.
"""

import threading

from tests.conftest import call_tool, parse_tool_result
from src.tools_extract import extract_structure_compact, list_form_fields

WORD_FIXTURE = "tests/fixtures/table_questionnaire.docx"
EXCEL_FIXTURE = "tests/fixtures/vendor_assessment.xlsx"
PDF_FIXTURE = "tests/fixtures/simple_form.pdf"


def _run_concurrent(mcp_session, calls):
    """Run tool calls concurrently and return {key: (status, result)} + errors.

    Each entry in calls is (tool_name, arguments, key, request_id).
    Returns (results_dict, errors_dict).
    """
    client, headers = mcp_session
    results = {}
    errors = {}

    def _worker(tool_name, arguments, key, request_id):
        try:
            resp = call_tool(client, headers, tool_name, arguments, request_id)
            parsed = parse_tool_result(resp)
            results[key] = (resp.status_code, parsed)
        except Exception as exc:
            errors[key] = exc

    threads = []
    for tool_name, arguments, key, request_id in calls:
        t = threading.Thread(
            target=_worker, args=(tool_name, arguments, key, request_id)
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    return results, errors


def test_concurrent_list_form_fields(mcp_session):
    """Three concurrent list_form_fields calls with different file types all succeed."""
    calls = [
        ("list_form_fields", {"file_path": WORD_FIXTURE}, "word", 1),
        ("list_form_fields", {"file_path": EXCEL_FIXTURE}, "excel", 2),
        ("list_form_fields", {"file_path": PDF_FIXTURE}, "pdf", 3),
    ]

    results, errors = _run_concurrent(mcp_session, calls)

    assert not errors, f"Threads raised errors: {errors}"
    assert len(results) == 3

    for key in ("word", "excel", "pdf"):
        status, parsed = results[key]
        assert status == 200
        assert "fields" in parsed

    # Verify each HTTP result matches its direct call
    direct_word = list_form_fields(file_path=WORD_FIXTURE)
    direct_excel = list_form_fields(file_path=EXCEL_FIXTURE)
    direct_pdf = list_form_fields(file_path=PDF_FIXTURE)

    assert results["word"][1] == direct_word
    assert results["excel"][1] == direct_excel
    assert results["pdf"][1] == direct_pdf


def test_concurrent_extract_structure(mcp_session):
    """Two concurrent extract_structure_compact calls with different files succeed."""
    calls = [
        ("extract_structure_compact", {"file_path": WORD_FIXTURE}, "word", 1),
        ("extract_structure_compact", {"file_path": EXCEL_FIXTURE}, "excel", 2),
    ]

    results, errors = _run_concurrent(mcp_session, calls)

    assert not errors, f"Threads raised errors: {errors}"
    assert len(results) == 2

    word_status, word_parsed = results["word"]
    excel_status, excel_parsed = results["excel"]

    assert word_status == 200
    assert excel_status == 200

    # Verify against direct calls
    direct_word = extract_structure_compact(file_path=WORD_FIXTURE)
    direct_excel = extract_structure_compact(file_path=EXCEL_FIXTURE)

    assert word_parsed == direct_word
    assert excel_parsed == direct_excel

    # No cross-contamination: word result has table IDs, excel has sheet IDs
    assert "T1-" in str(word_parsed.get("id_to_xpath", {}))
    assert "S1-" in str(excel_parsed.get("id_to_xpath", {}))


def test_concurrent_same_file(mcp_session):
    """Three concurrent calls for the same file all return identical results."""
    calls = [
        ("extract_structure_compact", {"file_path": WORD_FIXTURE}, "a", 1),
        ("extract_structure_compact", {"file_path": WORD_FIXTURE}, "b", 2),
        ("extract_structure_compact", {"file_path": WORD_FIXTURE}, "c", 3),
    ]

    results, errors = _run_concurrent(mcp_session, calls)

    assert not errors, f"Threads raised errors: {errors}"
    assert len(results) == 3

    for key in ("a", "b", "c"):
        assert results[key][0] == 200

    # All three results must be identical
    assert results["a"][1] == results["b"][1]
    assert results["b"][1] == results["c"][1]
