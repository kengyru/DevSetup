"""Validation and parsing for package lists taken from a setup file.

Everything that comes out of a .setup file is untrusted input. Only plain
pinned requirements are accepted:

    Django==5.2.4

Options (`--index-url ...`), URLs, git references, local paths and
editable installs are rejected, so a setup file cannot make pip execute
something else.
"""

import re

from app.models.package import PackageRequirement

_PIP_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"==(?P<version>[A-Za-z0-9][A-Za-z0-9.+!_-]*)$"
)

_NPM_NAME_RE = re.compile(
    r"^(?:@[A-Za-z0-9][A-Za-z0-9._-]*/)?"
    r"[A-Za-z0-9][A-Za-z0-9._-]*$"
)

_EXTENSION_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9-]*"
    r"\.[A-Za-z0-9][A-Za-z0-9.-]*$"
)

_WSL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_GIT_KEY_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z][A-Za-z0-9-]*)+$"
)

_PIP_SKIPPED_NAMES = {
    "pip",
    "setuptools",
    "wheel",
    "distribute",
}


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pip_requirement(
    line: str,
) -> PackageRequirement | None:
    """Parse a `name==version` line, returning None when unsafe."""

    if not line:
        return None

    line = line.strip()

    if not line or " " in line or "\t" in line:
        return None

    if "://" in line or line.startswith(("-", ".", "/", "\\")):
        return None

    match = _PIP_REQUIREMENT_RE.match(line)

    if not match:
        return None

    name = match.group("name")
    version = match.group("version")

    if normalize_package_name(name) in _PIP_SKIPPED_NAMES:
        return None

    return PackageRequirement(
        name=name,
        version=version,
        raw=f"{name}=={version}",
    )


def parse_pip_freeze(
    lines: list[str],
) -> list[PackageRequirement]:
    """Parse `pip freeze` output, dropping anything unsafe."""

    requirements = []
    seen = set()

    for line in lines:
        requirement = parse_pip_requirement(line)

        if requirement is None:
            continue

        if requirement.normalized_name in seen:
            continue

        seen.add(requirement.normalized_name)
        requirements.append(requirement)

    return requirements


def is_valid_npm_name(name: str) -> bool:
    return bool(name) and _NPM_NAME_RE.fullmatch(name) is not None


def is_valid_extension_id(extension_id: str) -> bool:
    return (
        bool(extension_id)
        and _EXTENSION_ID_RE.fullmatch(extension_id) is not None
    )


def is_valid_wsl_name(name: str) -> bool:
    return (
        bool(name)
        and _WSL_NAME_RE.fullmatch(name) is not None
        and not name.startswith("-")
    )


def is_valid_git_key(key: str) -> bool:
    return bool(key) and _GIT_KEY_RE.fullmatch(key) is not None
