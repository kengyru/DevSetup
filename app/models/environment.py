from dataclasses import dataclass, field
from typing import Optional

from app.models.application import InstalledApplication


@dataclass(frozen=True)
class WslDistribution:
    """A WSL distribution registered on this PC."""

    name: str
    version: Optional[int] = None
    state: Optional[str] = None

    @property
    def label(self) -> str:
        if self.version:
            return f"{self.name} (WSL {self.version})"

        return self.name

    def to_dict(self) -> dict:
        data = {"name": self.name}

        if self.version is not None:
            data["version"] = self.version

        if self.state:
            data["state"] = self.state

        return data

    @classmethod
    def from_dict(cls, data: object) -> "WslDistribution":
        if not isinstance(data, dict):
            raise ValueError(
                "Each WSL distribution must be a JSON object."
            )

        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "A WSL distribution entry is missing a valid 'name'."
            )

        version = data.get("version")

        if version is not None:
            if isinstance(version, str) and version.isdigit():
                version = int(version)

            if not isinstance(version, int) or version not in (1, 2):
                raise ValueError(
                    f"WSL distribution '{name}' has an invalid "
                    "'version' value."
                )

        state = data.get("state")

        if state is not None and not isinstance(state, str):
            raise ValueError(
                f"WSL distribution '{name}' has an invalid "
                "'state' value."
            )

        return cls(
            name=name.strip(),
            version=version,
            state=state.strip() if state else None,
        )


@dataclass
class TerminalSettings:
    """Read-only summary of the Windows Terminal configuration."""

    available: bool = False
    settings_path: Optional[str] = None
    default_profile: Optional[str] = None
    profiles: list[str] = field(default_factory=list)
    font_face: Optional[str] = None
    color_scheme: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "settings_path": self.settings_path,
            "default_profile": self.default_profile,
            "profiles": list(self.profiles),
            "font_face": self.font_face,
            "color_scheme": self.color_scheme,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: object) -> "TerminalSettings":
        if not isinstance(data, dict):
            raise ValueError(
                "The 'terminal' section must be a JSON object."
            )

        profiles = data.get("profiles", [])

        if not isinstance(profiles, list) or any(
            not isinstance(item, str) for item in profiles
        ):
            raise ValueError(
                "The 'terminal.profiles' field must be a list "
                "of strings."
            )

        return cls(
            available=bool(data.get("available", False)),
            settings_path=_optional_str(
                data,
                "settings_path",
                "terminal.settings_path",
            ),
            default_profile=_optional_str(
                data,
                "default_profile",
                "terminal.default_profile",
            ),
            profiles=profiles,
            font_face=_optional_str(
                data,
                "font_face",
                "terminal.font_face",
            ),
            color_scheme=_optional_str(
                data,
                "color_scheme",
                "terminal.color_scheme",
            ),
            message=_optional_str(
                data,
                "message",
                "terminal.message",
            ),
        )


def _optional_str(
    data: dict,
    key: str,
    label: str,
) -> Optional[str]:
    value = data.get(key)

    if value is not None and not isinstance(value, str):
        raise ValueError(f"'{label}' must be a string or null.")

    return value


@dataclass
class EnvironmentSnapshot:
    """Everything one scan of the PC produced."""

    applications: list[InstalledApplication] = field(
        default_factory=list
    )
    vscode_extensions: list[str] = field(default_factory=list)
    git_config: dict[str, str] = field(default_factory=dict)
    python_packages: list[str] = field(default_factory=list)
    npm_packages: list[str] = field(default_factory=list)
    wsl_distributions: list[WslDistribution] = field(
        default_factory=list
    )
    environment_variables: dict[str, str] = field(
        default_factory=dict
    )
    secret_environment_variables: list[str] = field(
        default_factory=list
    )
    terminal: TerminalSettings = field(
        default_factory=TerminalSettings
    )
    capabilities: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
