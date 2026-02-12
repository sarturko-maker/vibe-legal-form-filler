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

"""Word (.docx) XML extraction — read document.xml from a .docx archive.

Shared by word.py, word_verifier.py, and word_location_validator.py.
Provides the low-level .docx-to-XML extraction that all Word handlers need.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from lxml import etree

from src.xml_utils import NAMESPACES, SECURE_PARSER


def read_document_xml(file_bytes: bytes) -> bytes:
    """Extract word/document.xml from a .docx ZIP archive."""
    with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
        return zf.read("word/document.xml")


def get_body_xml(file_bytes: bytes) -> str:
    """Extract the <w:body> XML string from a .docx file."""
    doc_xml = read_document_xml(file_bytes)
    root = etree.fromstring(doc_xml, SECURE_PARSER)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("No <w:body> element found in document.xml")
    return etree.tostring(body, encoding="unicode")
