"""Server-side validation and sanitisation of `.setup` payloads.

This module is deliberately independent from the desktop application.
The backend does not import ``app`` and never uses PySide6, winget,
pip, npm or Windows APIs. It only understands the JSON on-disk format.

Rules
-----
* format versions 1 and 2 are accepted; a missing ``format_version``
  means version 1, exactly like the desktop importer;
* the payload must be a JSON object of at most 2 MB;
* every array and object has a size limit;
* unknown fields are dropped instead of stored;
* Git settings outside the safe allowlist are dropped;
* environment variables that look secret are not stored, only their
  names are kept for display;
* nothing is ever executed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .security import (
    is_protected_name,
    is_secret_name,
    is_valid_environment_name,
)

MAX_SETUP_BYTES = 2 * 1024 * 1024

MAX_JSON_DEPTH = 8
MAX_JSON_ITEMS = 20_000
MAX_OBJECT_KEYS = 1_000
MAX_ARRAY_LENGTH = 1_000

MAX_APPLICATIONS = 100
MAX_EXTENSIONS_PER_APP = 300
MAX_PYTHON_PACKAGES = 500
MAX_NPM_PACKAGES = 500
MAX_WSL_DISTRIBUTIONS = 50
MAX_GIT_SETTINGS = 100
MAX_ENVIRONMENT_VARIABLES = 200
MAX_SECRET_VARIABLES = 200
MAX_TERMINAL_PROFILES = 100

MAX_APP_NAME_LENGTH = 100
MAX_VERSION_LENGTH = 100
MAX_PATH_LENGTH = 1_024
MAX_PACKAGE_ID_LENGTH = 200
MAX_EXTENSION_ID_LENGTH = 200
MAX_PACKAGE_ENTRY_LENGTH = 214
MAX_GIT_VALUE_LENGTH = 2_000
MAX_ENV_NAME_LENGTH = 128
MAX_ENV_VALUE_LENGTH = 4_000
MAX_WSL_NAME_LENGTH = 100
MAX_WSL_STATE_LENGTH = 50
MAX_TERMINAL_TEXT_LENGTH = 500
MAX_TERMINAL_PATH_LENGTH = 1_024

SAFE_GIT_KEYS = frozenset(
    {
        "user.name",
        "user.email",
        "core.editor",
        "core.autocrlf",
        "core.eol",
        "init.defaultbranch",
        "pull.rebase",
        "pull.ff",
        "push.default",
        "push.autosetupremote",
        "merge.conflictstyle",
        "fetch.prune",
    }
)

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

_PIP_SKIPPED_NAMES = {
    "pip",
    "setuptools",
    "wheel",
    "distribute",
}

_MISSING = object()


class SetupValidationError(Exception):
    """Raised when a setup payload must be rejected."""

    def __init__(self, detail):
        self.detail = detail
        super().__init__(str(detail))


@dataclass(frozen=True)
class SanitizedSetup:
    format_version: int
    data: dict


def _error(path: str, message: str) -> None:
    raise SetupValidationError({path: [message]})


def _list(value, path: str, limit: int) -> list:
    if not isinstance(value, list):
        _error(path, "must be a list.")

    if len(value) > limit:
        _error(path, f"must contain at most {limit} items.")

    return value


def _string(
    value,
    path: str,
    max_length: int,
    *,
    default=_MISSING,
    strip: bool = False,
    allow_blank: bool = True,
) -> str:
    if value is _MISSING or value is None:
        if default is _MISSING:
            _error(path, "is required.")
        return default

    if not isinstance(value, str):
        _error(path, "must be a string.")

    if strip:
        value = value.strip()

    if not allow_blank and not value:
        _error(path, "must not be blank.")

    if len(value) > max_length:
        _error(
            path,
            f"must be at most {max_length} characters.",
        )

    if "\x00" in value:
        _error(path, "must not contain NUL characters.")

    return value


def _optional_string(value, path: str, max_length: int):
    if value is None:
        return None

    return _string(value, path, max_length)


def _check_json_shape(value, depth: int, counter: list[int]) -> None:
    if depth > MAX_JSON_DEPTH:
        _error("data", "is nested too deeply.")

    counter[0] += 1

    if counter[0] > MAX_JSON_ITEMS:
        _error("data", "contains too many values.")

    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_KEYS:
            _error("data", "contains an object with too many keys.")

        for key, item in value.items():
            if not isinstance(key, str):
                _error("data", "must use string keys.")

            _check_json_shape(item, depth + 1, counter)

        return

    if isinstance(value, list):
        if len(value) > MAX_ARRAY_LENGTH:
            _error("data", "contains an array with too many items.")

        for item in value:
            _check_json_shape(item, depth + 1, counter)

        return

    if value is None or isinstance(value, (bool, int, float, str)):
        return

    _error("data", "must contain only JSON values.")


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _is_valid_extension_id(extension_id: str) -> bool:
    return (
        bool(extension_id)
        and _EXTENSION_ID_RE.fullmatch(extension_id) is not None
    )


def _is_valid_wsl_name(name: str) -> bool:
    return (
        bool(name)
        and _WSL_NAME_RE.fullmatch(name) is not None
        and not name.startswith("-")
    )


def _extension_list(value, path: str) -> list[str]:
    items = _list(value, path, MAX_EXTENSIONS_PER_APP)
    result: list[str] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, str):
            continue

        extension_id = item.strip()

        if len(extension_id) > MAX_EXTENSION_ID_LENGTH:
            continue

        if not _is_valid_extension_id(extension_id):
            continue

        key = extension_id.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(extension_id)

    return sorted(result)


def _applications(value) -> list[dict]:
    if value is None:
        return []

    items = _list(value, "data.applications", MAX_APPLICATIONS)
    result: list[dict] = []

    for index, item in enumerate(items):
        path = f"data.applications.{index}"

        if not isinstance(item, dict):
            _error(path, "must be an object.")

        name = _string(
            item.get("name"),
            f"{path}.name",
            MAX_APP_NAME_LENGTH,
            strip=True,
            allow_blank=False,
        )

        installed = item.get("installed", False)

        if not isinstance(installed, bool):
            _error(f"{path}.installed", "must be a boolean.")

        default_version = (
            "Unknown" if installed else "Not installed"
        )
        version = _string(
            item.get("version"),
            f"{path}.version",
            MAX_VERSION_LENGTH,
            default=default_version,
        )

        entry = {
            "name": name,
            "version": version,
            "path": _optional_string(
                item.get("path"),
                f"{path}.path",
                MAX_PATH_LENGTH,
            ),
            "installed": installed,
        }

        package_id = item.get("package_id")

        if package_id is not None:
            entry["package_id"] = _string(
                package_id,
                f"{path}.package_id",
                MAX_PACKAGE_ID_LENGTH,
            )

        if "extensions" in item:
            extensions = _extension_list(
                item["extensions"],
                f"{path}.extensions",
            )

            if extensions:
                entry["extensions"] = extensions

        result.append(entry)

    return result


def _git_config(value) -> dict[str, str]:
    if value is None:
        return {}

    if not isinstance(value, dict):
        _error("data.git_config", "must be an object.")

    if len(value) > MAX_GIT_SETTINGS:
        _error(
            "data.git_config",
            f"must contain at most {MAX_GIT_SETTINGS} settings.",
        )

    result: dict[str, str] = {}

    for key, setting_value in value.items():
        if not isinstance(key, str):
            continue

        key = key.strip().lower()

        if key not in SAFE_GIT_KEYS:
            continue

        if not isinstance(setting_value, str):
            continue

        if len(setting_value) > MAX_GIT_VALUE_LENGTH:
            continue

        if "\x00" in setting_value:
            continue

        # The desktop refuses to apply multi-line Git values; storing them
        # would only create a setup that cannot be restored.
        if "\r" in setting_value or "\n" in setting_value:
            continue

        result[key] = setting_value

    return dict(sorted(result.items()))


def _python_packages(value) -> list[str]:
    if value is None:
        return []

    items = _list(
        value,
        "data.python_packages",
        MAX_PYTHON_PACKAGES,
    )
    result: list[str] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, str):
            continue

        line = item.strip()

        if (
            not line
            or len(line) > MAX_PACKAGE_ENTRY_LENGTH
            or " " in line
            or "\t" in line
        ):
            continue

        if "://" in line or line.startswith(("-", ".", "/", "\\")):
            continue

        match = _PIP_REQUIREMENT_RE.match(line)

        if match is None:
            continue

        name = match.group("name")
        version = match.group("version")
        normalized = _normalize_package_name(name)

        if normalized in _PIP_SKIPPED_NAMES:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(f"{name}=={version}")

    return result


def _npm_packages(value) -> list[str]:
    if value is None:
        return []

    items = _list(value, "data.npm_packages", MAX_NPM_PACKAGES)
    result: list[str] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, str):
            continue

        name = item.strip()

        if (
            not name
            or len(name) > MAX_PACKAGE_ENTRY_LENGTH
            or _NPM_NAME_RE.fullmatch(name) is None
        ):
            continue

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(name)

    return result


def _wsl_distributions(value) -> list[dict]:
    if value is None:
        return []

    items = _list(
        value,
        "data.wsl_distributions",
        MAX_WSL_DISTRIBUTIONS,
    )
    result: list[dict] = []
    seen: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        name = item.get("name")

        if not isinstance(name, str):
            continue

        name = name.strip()

        if (
            not name
            or len(name) > MAX_WSL_NAME_LENGTH
            or not _is_valid_wsl_name(name)
        ):
            continue

        key = name.lower()

        if key in seen:
            continue

        entry = {"name": name}
        version = item.get("version")

        if version is not None:
            if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version not in (1, 2)
            ):
                continue

            entry["version"] = version

        state = item.get("state")

        if state is not None:
            if (
                not isinstance(state, str)
                or len(state) > MAX_WSL_STATE_LENGTH
                or "\x00" in state
            ):
                state = None

            if state:
                entry["state"] = state

        seen.add(key)
        result.append(entry)

    return result


def _declared_secret_names(value) -> set[str]:
    if value is None:
        return set()

    items = _list(
        value,
        "data.secret_environment_variables",
        MAX_SECRET_VARIABLES,
    )
    result: set[str] = set()

    for item in items:
        if not isinstance(item, str):
            continue

        name = item.strip()

        if (
            not name
            or len(name) > MAX_ENV_NAME_LENGTH
            or not is_valid_environment_name(name)
        ):
            continue

        result.add(name)

    return result


def _environment_variables(
    value,
    declared_secrets: set[str],
) -> tuple[dict[str, str], list[str]]:
    if value is None:
        value = {}

    if not isinstance(value, dict):
        _error("data.environment_variables", "must be an object.")

    if len(value) > MAX_ENVIRONMENT_VARIABLES:
        _error(
            "data.environment_variables",
            "must contain at most "
            f"{MAX_ENVIRONMENT_VARIABLES} variables.",
        )

    safe: dict[str, str] = {}
    secrets = set(declared_secrets)

    for name, variable_value in value.items():
        if not isinstance(name, str):
            continue

        name = name.strip()

        if (
            not name
            or len(name) > MAX_ENV_NAME_LENGTH
            or not is_valid_environment_name(name)
        ):
            continue

        if name in declared_secrets or is_secret_name(name):
            # The value is deliberately discarded. Only the name is kept
            # so the desktop UI can show "Secret - not backed up".
            secrets.add(name)
            continue

        if is_protected_name(name):
            continue

        if not isinstance(variable_value, str):
            continue

        if (
            len(variable_value) > MAX_ENV_VALUE_LENGTH
            or "\x00" in variable_value
        ):
            continue

        safe[name] = variable_value

    return dict(sorted(safe.items())), sorted(secrets)


def _terminal_settings(value) -> dict:
    empty = {
        "available": False,
        "settings_path": None,
        "default_profile": None,
        "profiles": [],
        "font_face": None,
        "color_scheme": None,
        "message": None,
    }

    if value is None:
        return empty

    if not isinstance(value, dict):
        _error("data.terminal", "must be an object.")

    available = value.get("available", False)

    if not isinstance(available, bool):
        _error("data.terminal.available", "must be a boolean.")

    profiles = value.get("profiles", [])

    if not isinstance(profiles, list):
        _error("data.terminal.profiles", "must be a list.")

    if len(profiles) > MAX_TERMINAL_PROFILES:
        _error(
            "data.terminal.profiles",
            f"must contain at most {MAX_TERMINAL_PROFILES} items.",
        )

    clean_profiles: list[str] = []

    for profile in profiles:
        if (
            isinstance(profile, str)
            and profile
            and len(profile) <= MAX_EXTENSION_ID_LENGTH
            and "\x00" not in profile
        ):
            clean_profiles.append(profile)

    return {
        "available": available,
        "settings_path": _optional_string(
            value.get("settings_path"),
            "data.terminal.settings_path",
            MAX_TERMINAL_PATH_LENGTH,
        ),
        "default_profile": _optional_string(
            value.get("default_profile"),
            "data.terminal.default_profile",
            MAX_EXTENSION_ID_LENGTH,
        ),
        "profiles": clean_profiles,
        "font_face": _optional_string(
            value.get("font_face"),
            "data.terminal.font_face",
            MAX_EXTENSION_ID_LENGTH,
        ),
        "color_scheme": _optional_string(
            value.get("color_scheme"),
            "data.terminal.color_scheme",
            MAX_EXTENSION_ID_LENGTH,
        ),
        "message": _optional_string(
            value.get("message"),
            "data.terminal.message",
            MAX_TERMINAL_TEXT_LENGTH,
        ),
    }


def _attach_top_level_extensions(
    applications: list[dict],
    extensions: list[str],
) -> list[str]:
    """Merge top-level extensions into the VS Code entry when possible.

    The desktop exporter normally writes extensions inside the VS Code
    application entry, but its importer also accepts a top-level list.
    Keeping both forms compatible avoids losing data.
    """

    if not extensions:
        return []

    for application in applications:
        if application["name"].strip().lower() != "vs code":
            continue

        merged = {
            *application.get("extensions", []),
            *extensions,
        }
        application["extensions"] = sorted(
            merged,
            key=str.lower,
        )
        return []

    return extensions


def validate_setup_payload(raw) -> SanitizedSetup:
    """Validate and sanitize one setup payload.

    Raises :class:`SetupValidationError` with a field -> messages mapping.
    Returns a :class:`SanitizedSetup` ready to be stored.
    """

    if not isinstance(raw, dict):
        _error("data", "must be a JSON object.")

    _check_json_shape(raw, 0, [0])

    try:
        encoded = json.dumps(
            raw,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        _error("data", "must contain only JSON values.")

    if len(encoded) > MAX_SETUP_BYTES:
        _error("data", "must not exceed 2 MB.")

    format_version = raw.get("format_version", 1)

    if isinstance(format_version, bool) or not isinstance(
        format_version,
        int,
    ):
        _error("data.format_version", "must be an integer.")

    if format_version not in (1, 2):
        _error(
            "data.format_version",
            "unsupported format version; expected 1 or 2.",
        )

    applications = _applications(raw.get("applications"))

    if format_version == 1:
        # Version 1 setups only ever contained applications.
        return SanitizedSetup(
            format_version=1,
            data={"applications": applications},
        )

    declared_secrets = _declared_secret_names(
        raw.get("secret_environment_variables")
    )
    environment_variables, secret_variables = (
        _environment_variables(
            raw.get("environment_variables"),
            declared_secrets,
        )
    )

    top_level_extensions = []

    if "vscode_extensions" in raw:
        top_level_extensions = _extension_list(
            raw["vscode_extensions"],
            "data.vscode_extensions",
        )

    remaining_extensions = _attach_top_level_extensions(
        applications,
        top_level_extensions,
    )

    data = {
        "applications": applications,
        "git_config": _git_config(raw.get("git_config")),
        "python_packages": _python_packages(
            raw.get("python_packages")
        ),
        "npm_packages": _npm_packages(raw.get("npm_packages")),
        "wsl_distributions": _wsl_distributions(
            raw.get("wsl_distributions")
        ),
        "environment_variables": environment_variables,
        "secret_environment_variables": secret_variables,
        "terminal": _terminal_settings(raw.get("terminal")),
    }

    if remaining_extensions:
        data["vscode_extensions"] = sorted(
            remaining_extensions,
            key=str.lower,
        )

    return SanitizedSetup(
        format_version=format_version,
        data=data,
    )
