import re
from typing import Iterable

from app.core.secrets import is_protected_name, is_secret_name
from app.scanner.base import BaseCollector

try:
    import winreg
except ImportError:  # pragma: no cover - Windows only project
    winreg = None

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_MAX_VALUE_LENGTH = 4000


def _read_user_values() -> Iterable[tuple[str, object, int]]:
    """Yield (name, value, type) from HKCU\\Environment."""

    if winreg is None:
        return []

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ,
        )

    except OSError:
        return []

    values = []

    with key:
        index = 0

        while True:
            try:
                name, value, value_type = winreg.EnumValue(
                    key,
                    index,
                )

            except OSError:
                break

            values.append((name, value, value_type))
            index += 1

    return values


class EnvironmentScanner(BaseCollector):
    """Saves safe user environment variables and lists skipped secrets."""

    NAME = "Environment variables"

    def __init__(self):
        super().__init__()
        self.secrets: list[str] = []

    def scan(self) -> dict[str, str]:
        if winreg is None:
            self.available = False
            self.secrets = []
            return {}

        values = list(_read_user_values())

        saved: dict[str, str] = {}
        secrets: set[str] = set()

        for name, value, _value_type in values:
            if not isinstance(name, str) or not isinstance(
                value, str
            ):
                continue

            if is_secret_name(name):
                secrets.add(name)
                continue

            if is_protected_name(name):
                continue

            if not _NAME_RE.fullmatch(name):
                continue

            if len(value) > _MAX_VALUE_LENGTH:
                continue

            if "\x00" in value:
                continue

            saved[name] = value

        self.secrets = sorted(secrets)

        return dict(sorted(saved.items()))
