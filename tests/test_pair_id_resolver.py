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

"""Tests for pair_id resolution and cross-check logic.

Verifies that resolve_pair_ids returns correct xpaths for Word, Excel,
and PDF pair_ids, omits unknown pair_ids, and that cross_check_xpaths
produces warnings only when both xpath and pair_id are provided and they
disagree.
"""

from pathlib import Path

import pytest

from src.models import FileType

FIXTURES = Path(__file__).parent / "fixtures"


# ── resolve_pair_ids: Word ────────────────────────────────────────────────────


def test_resolve_word_pair_ids_returns_xpaths():
    """Known pair_ids from table_questionnaire.docx resolve to xpaths."""
    from src.pair_id_resolver import resolve_pair_ids

    fb = (FIXTURES / "table_questionnaire.docx").read_bytes()
    result = resolve_pair_ids(fb, FileType.WORD, ["T1-R2-C2", "T1-R3-C1"])

    assert "T1-R2-C2" in result
    assert "T1-R3-C1" in result
    # Xpaths should match what word_indexer produces
    assert result["T1-R2-C2"] == "./w:tbl[1]/w:tr[2]/w:tc[2]"
    assert result["T1-R3-C1"] == "./w:tbl[1]/w:tr[3]/w:tc[1]"


def test_resolve_word_unknown_pair_id_omitted():
    """Unknown pair_ids are not in the returned dict."""
    from src.pair_id_resolver import resolve_pair_ids

    fb = (FIXTURES / "table_questionnaire.docx").read_bytes()
    result = resolve_pair_ids(fb, FileType.WORD, ["T99-R1-C1", "T1-R2-C2"])

    assert "T99-R1-C1" not in result
    assert "T1-R2-C2" in result


# ── resolve_pair_ids: Excel ───────────────────────────────────────────────────


def test_resolve_excel_pair_ids_returns_identity_xpaths():
    """Excel pair_ids resolve to themselves (identity mapping)."""
    from src.pair_id_resolver import resolve_pair_ids

    fb = (FIXTURES / "vendor_assessment.xlsx").read_bytes()
    result = resolve_pair_ids(fb, FileType.EXCEL, ["S1-R2-C2", "S1-R3-C1"])

    assert result["S1-R2-C2"] == "S1-R2-C2"
    assert result["S1-R3-C1"] == "S1-R3-C1"


# ── resolve_pair_ids: PDF ────────────────────────────────────────────────────


def test_resolve_pdf_pair_ids_returns_field_names():
    """PDF pair_ids resolve to native field names."""
    from src.pair_id_resolver import resolve_pair_ids

    fb = (FIXTURES / "simple_form.pdf").read_bytes()
    result = resolve_pair_ids(fb, FileType.PDF, ["F1", "F2"])

    assert result["F1"] == "full_name"
    assert result["F2"] == "email"


# ── cross_check_xpaths ──────────────────────────────────────────────────────


def test_cross_check_matching_xpaths_returns_empty():
    """No warnings when agent xpath matches resolved xpath."""
    from src.pair_id_resolver import cross_check_xpaths

    answers = [{"pair_id": "T1-R2-C2", "xpath": "./w:tbl[1]/w:tr[2]/w:tc[2]"}]
    resolved = {"T1-R2-C2": "./w:tbl[1]/w:tr[2]/w:tc[2]"}

    warnings = cross_check_xpaths(answers, resolved)
    assert warnings == []


def test_cross_check_mismatching_xpaths_returns_warning():
    """Warning generated when agent xpath differs from resolved xpath."""
    from src.pair_id_resolver import cross_check_xpaths

    answers = [{"pair_id": "T1-R2-C2", "xpath": "/wrong/path"}]
    resolved = {"T1-R2-C2": "./w:tbl[1]/w:tr[2]/w:tc[2]"}

    warnings = cross_check_xpaths(answers, resolved)
    assert len(warnings) == 1
    assert "T1-R2-C2" in warnings[0]
    assert "/wrong/path" in warnings[0]
    assert "./w:tbl[1]/w:tr[2]/w:tc[2]" in warnings[0]
    assert "using resolved" in warnings[0]


def test_cross_check_no_agent_xpath_returns_empty():
    """No warning when only pair_id is provided (no agent xpath)."""
    from src.pair_id_resolver import cross_check_xpaths

    answers = [{"pair_id": "T1-R2-C2"}]
    resolved = {"T1-R2-C2": "./w:tbl[1]/w:tr[2]/w:tc[2]"}

    warnings = cross_check_xpaths(answers, resolved)
    assert warnings == []


def test_cross_check_no_resolved_xpath_returns_empty():
    """No warning when pair_id not in resolved dict."""
    from src.pair_id_resolver import cross_check_xpaths

    answers = [{"pair_id": "T99-R1-C1", "xpath": "/some/path"}]
    resolved = {}

    warnings = cross_check_xpaths(answers, resolved)
    assert warnings == []
