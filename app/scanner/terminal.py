import json
import os
import re
from pathlib import Path

from app.models.environment import TerminalSettings
from app.scanner.base import BaseCollector

_MAX_SETTINGS_SIZE = 4 * 1024 * 1024


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas.

    Windows Terminal settings.json is JSON with comments, while Python's
    json module only accepts strict JSON.
    """

    result = []
    index = 0
    length = len(text)
    in_string = False
    escaped = False

    while index < length:
        character = text[index]

        if in_string:
            result.append(character)

            if escaped:
                escaped = False

            elif character == "\\":
                escaped = True

            elif character == '"':
                in_string = False

            index += 1
            continue

        if character == '"':
            in_string = True
            result.append(character)
            index += 1
            continue

        if character == "/" and index + 1 < length:
            next_character = text[index + 1]

            if next_character == "/":
                while (
                    index < length
                    and text[index] not in "\r\n"
                ):
                    index += 1

                continue

            if next_character == "*":
                index += 2

                while (
                    index + 1 < length
                    and not (
                        text[index] == "*"
                        and text[index + 1] == "/"
                    )
                ):
                    index += 1

                index += 2
                continue

        result.append(character)
        index += 1

    cleaned = "".join(result)

    return re.sub(r",(\s*[}\]])", r"\1", cleaned)


def find_settings_path() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")

    if not local_app_data:
        return None

    base = Path(local_app_data)
    packages = base / "Packages"

    candidates: list[Path] = []

    for pattern in (
        "Microsoft.WindowsTerminal_*/LocalState/settings.json",
        "Microsoft.WindowsTerminalPreview_*/LocalState/settings.json",
    ):
        candidates.extend(
            sorted(packages.glob(pattern), reverse=True)
        )

    candidates.append(
        base / "Microsoft" / "Windows Terminal" / "settings.json"
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def parse_terminal_settings(
    text: str,
    settings_path: str,
) -> TerminalSettings:
    data = json.loads(strip_jsonc(text))

    if not isinstance(data, dict):
        raise ValueError(
            "Windows Terminal settings must be a JSON object."
        )

    profiles_section = data.get("profiles")

    defaults = {}
    raw_profiles = []

    if isinstance(profiles_section, dict):
        defaults = profiles_section.get("defaults") or {}

        if not isinstance(defaults, dict):
            defaults = {}

        raw_profiles = profiles_section.get("list") or []

    elif isinstance(profiles_section, list):
        raw_profiles = profiles_section

    if not isinstance(raw_profiles, list):
        raw_profiles = []

    profile_names = []

    for profile in raw_profiles:
        if not isinstance(profile, dict):
            continue

        name = profile.get("name")

        if isinstance(name, str) and name.strip():
            profile_names.append(name.strip())

    default_guid = data.get("defaultProfile")
    default_profile = None

    if isinstance(default_guid, str):
        for profile in raw_profiles:
            if not isinstance(profile, dict):
                continue

            guid = profile.get("guid")

            if (
                isinstance(guid, str)
                and guid.lower() == default_guid.lower()
            ):
                name = profile.get("name")

                if isinstance(name, str):
                    default_profile = name.strip()

                break

    font = defaults.get("font")
    font_face = None

    if isinstance(font, dict):
        face = font.get("face")

        if isinstance(face, str):
            font_face = face

    color_scheme = defaults.get("colorScheme")

    if not isinstance(color_scheme, str):
        color_scheme = None

    return TerminalSettings(
        available=True,
        settings_path=settings_path,
        default_profile=default_profile,
        profiles=profile_names[:50],
        font_face=font_face,
        color_scheme=color_scheme,
    )


class TerminalScanner(BaseCollector):
    """Read-only detection of Windows Terminal settings.

    Full restore is intentionally not implemented: profile GUIDs,
    starting directories and machine specific paths do not transfer
    safely between computers.
    """

    NAME = "Terminal settings"

    def scan(self) -> TerminalSettings:
        path = find_settings_path()

        if path is None:
            self.available = False

            return TerminalSettings(
                available=False,
                message=(
                    "Windows Terminal settings were not found."
                ),
            )

        try:
            if path.stat().st_size > _MAX_SETTINGS_SIZE:
                raise ValueError("settings.json is too large.")

            text = path.read_text(encoding="utf-8-sig")

        except (OSError, ValueError) as error:
            return TerminalSettings(
                available=False,
                settings_path=str(path),
                message=f"Could not read settings.json: {error}",
            )

        try:
            return parse_terminal_settings(text, str(path))

        except (ValueError, json.JSONDecodeError) as error:
            return TerminalSettings(
                available=False,
                settings_path=str(path),
                message=(
                    f"Could not parse settings.json: {error}"
                ),
            )
