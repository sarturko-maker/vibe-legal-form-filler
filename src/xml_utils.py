"""OOXML utilities — re-export barrel for snippet matching, formatting, and
validation modules.

This module re-exports all public symbols so that existing imports like
`from src.xml_utils import ...` continue to work without changes.
"""

from src.xml_snippet_matching import (  # noqa: F401
    NAMESPACES,
    find_snippet_in_body,
    parse_snippet,
)

from src.xml_formatting import (  # noqa: F401
    build_run_xml,
    extract_formatting,
)

from src.xml_validation import is_well_formed_ooxml  # noqa: F401
