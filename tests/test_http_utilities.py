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

"""HTTP tests for list_form_fields utility across Word, Excel, and PDF.

Proves that the list_form_fields utility tool returns correct results
when called over HTTP for all three file types (TEST-03), and that it
handles nonexistent files gracefully.
"""

import json

from tests.conftest import call_tool, parse_tool_result
from src.tools_extract import list_form_fields

WORD_FIXTURE = "tests/fixtures/table_questionnaire.docx"
EXCEL_FIXTURE = "tests/fixtures/vendor_assessment.xlsx"
PDF_FIXTURE = "tests/fixtures/simple_form.pdf"


def test_list_form_fields_word(mcp_session):
    """list_form_fields over HTTP returns same result as direct call for Word."""
    client, headers = mcp_session
    args = {"file_path": WORD_FIXTURE}

    resp = call_tool(client, headers, "list_form_fields", args)
    assert resp.status_code == 200
    http_result = parse_tool_result(resp)

    direct = list_form_fields(file_path=WORD_FIXTURE)

    assert http_result == direct
    assert "fields" in http_result
    assert len(http_result["fields"]) > 0


def test_list_form_fields_excel(mcp_session):
    """list_form_fields over HTTP returns same result as direct call for Excel."""
    client, headers = mcp_session
    args = {"file_path": EXCEL_FIXTURE}

    resp = call_tool(client, headers, "list_form_fields", args)
    assert resp.status_code == 200
    http_result = parse_tool_result(resp)

    direct = list_form_fields(file_path=EXCEL_FIXTURE)

    assert http_result == direct
    assert "fields" in http_result
    assert len(http_result["fields"]) > 0


def test_list_form_fields_pdf(mcp_session):
    """list_form_fields over HTTP returns same result as direct call for PDF."""
    client, headers = mcp_session
    args = {"file_path": PDF_FIXTURE}

    resp = call_tool(client, headers, "list_form_fields", args)
    assert resp.status_code == 200
    http_result = parse_tool_result(resp)

    direct = list_form_fields(file_path=PDF_FIXTURE)

    assert http_result == direct
    assert "fields" in http_result
    assert len(http_result["fields"]) > 0


def test_list_form_fields_nonexistent_file(mcp_session):
    """list_form_fields with nonexistent file returns error gracefully."""
    client, headers = mcp_session
    args = {"file_path": "tests/fixtures/does_not_exist.docx"}

    resp = call_tool(client, headers, "list_form_fields", args)
    assert resp.status_code == 200

    # The response should contain an error (isError=true in the result)
    for line in resp.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        msg = json.loads(payload)
        if "result" not in msg:
            continue
        result = msg["result"]
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "not found" in text.lower() or "error" in text.lower()
        return

    raise AssertionError("No error result found in SSE response")
