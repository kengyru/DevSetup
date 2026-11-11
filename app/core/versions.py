"""Helpers for reading and comparing version strings.

Scanners get their version text from different tools, for example:

    "Python 3.13.16"
    "git version 2.56.0.windows.2"
    "1.142.0"

The helpers below make these formats comparable without changing what is
stored in the setup file.
"""

import re

_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")


def extract_version(text: str) -> str:
    """Extract the numeric version part of a version string."""

    if not text:
        return ""

    match = _VERSION_RE.search(text)

    if match:
        return match.group(0)

    return text.strip()


def has_version(text: str) -> bool:
    """Return True when the text contains a numeric version."""

    return bool(text) and _VERSION_RE.search(text) is not None



def versions_match(saved_version: str, current_version: str) -> bool:
    """Return True when two version strings describe the same version."""

    saved_key = extract_version(saved_version).lower()
    current_key = extract_version(current_version).lower()

    if not saved_key or not current_key:
        return False

    return saved_key == current_key
