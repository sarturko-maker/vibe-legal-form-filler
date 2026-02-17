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

"""OOXML utilities — re-export barrel for snippet matching, formatting, and
validation modules.

This module re-exports all public symbols so that existing imports like
`from src.xml_utils import ...` continue to work without changes.
"""

from src.xml_snippet_matching import (  # noqa: F401
    NAMESPACES,
    SECURE_PARSER,
    build_xpath,
    find_snippet_in_body,
    parse_snippet,
)

from src.xml_formatting import (  # noqa: F401
    build_run_xml,
    extract_formatting,
    extract_formatting_from_element,
)

from src.xml_validation import is_well_formed_ooxml  # noqa: F401
