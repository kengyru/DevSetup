from dataclasses import dataclass
from typing import Optional

from app.core.packages import get_package_id


@dataclass
class InstalledApplication:
    """A development tool found on the PC or stored in a setup file."""

    name: str
    version: str
    path: Optional[str] = None
    installed: bool = False
    package_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize the application for the .setup file."""

        data = {
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "installed": self.installed,
        }

        if self.package_id:
            data["package_id"] = self.package_id

        return data

    @classmethod
    def from_dict(cls, data: object) -> "InstalledApplication":
        """Build an application from a parsed .setup file entry."""

        if not isinstance(data, dict):
            raise ValueError(
                "Each entry in 'applications' must be a JSON object."
            )

        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "An application entry is missing a valid 'name'."
            )

        path = data.get("path")

        if path is not None and not isinstance(path, str):
            raise ValueError(
                f"Application '{name}' has an invalid 'path' value."
            )

        installed = data.get("installed", False) is True

        version = data.get("version")

        if not isinstance(version, str) or not version.strip():
            version = "Unknown" if installed else "Not installed"

        # The 'package_id' stored in a setup file is informational only.
        # Restore derives the id from the local allowlist, so a modified
        # file cannot make winget install an arbitrary package.
        package_id = get_package_id(name)

        return cls(
            name=name.strip(),
            version=version.strip(),
            path=path,
            installed=installed,
            package_id=package_id,
        )
