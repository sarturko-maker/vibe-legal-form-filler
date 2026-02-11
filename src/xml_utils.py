"""OOXML utilities — re-export barrel for snippet matching and formatting modules.

This module re-exports all public symbols from xml_snippet_matching and
xml_formatting so that existing imports like `from src.xml_utils import ...`
continue to work without changes.
"""

from src.xml_snippet_matching import (  # noqa: F401
    NAMESPACES,
    find_snippet_in_body,
    parse_snippet,
)

# Backwards-compatible alias: old code imports _parse_snippet
_parse_snippet = parse_snippet

from src.xml_formatting import (  # noqa: F401
    build_run_xml,
    extract_formatting,
    is_well_formed_ooxml,
)

# Re-export normalise_whitespace until dead code is removed in step 3
from src.xml_snippet_matching import _elements_structurally_equal  # noqa: F401


def normalise_whitespace(xml_string: str) -> str:
    """Normalise whitespace in an XML string for comparison purposes.

    Collapses runs of whitespace between tags, strips leading/trailing whitespace,
    and normalises whitespace within text nodes.
    """
    import re
    result = re.sub(r">\s+<", "><", xml_string.strip())
    result = re.sub(r"\s+", " ", result)
    return result
