import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PackageRequirement:
    """A pinned package from a setup file or from the current PC."""

    name: str
    version: str | None
    raw: str

    @property
    def normalized_name(self) -> str:
        return re.sub(
            r"[-_.]+",
            "-",
            self.name,
        ).lower()

    @property
    def label(self) -> str:
        if self.version:
            return f"{self.name}=={self.version}"

        return self.name
