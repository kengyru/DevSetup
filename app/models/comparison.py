from dataclasses import dataclass
from enum import Enum

from app.models.application import InstalledApplication
from app.models.environment import (
    EnvironmentSnapshot,
    TerminalSettings,
    WslDistribution,
)
from app.models.package import PackageRequirement


class ComparisonStatus(str, Enum):
    """Result of comparing a saved setup with the current PC."""

    INSTALLED = "installed"
    MISSING = "missing"
    VERSION_MISMATCH = "version_mismatch"


@dataclass(frozen=True)
class ComparisonItem:
    """One saved application together with its state on the current PC."""

    saved: InstalledApplication
    current: InstalledApplication | None
    status: ComparisonStatus

    @property
    def name(self) -> str:
        return self.saved.name

    @property
    def current_version(self) -> str:
        if self.current is None or not self.current.installed:
            return "Not installed"

        return self.current.version

    @property
    def current_path(self) -> str | None:
        if self.current is None or not self.current.installed:
            return None

        return self.current.path

    @property
    def is_missing(self) -> bool:
        return self.status is ComparisonStatus.MISSING


@dataclass(frozen=True)
class ExtensionsComparison:
    saved: tuple[str, ...]
    current: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def in_sync(self) -> bool:
        return not self.missing

    @property
    def difference_count(self) -> int:
        return len(self.missing)


@dataclass(frozen=True)
class GitConfigComparison:
    saved: dict[str, str]
    current: dict[str, str]
    missing: dict[str, str]
    mismatched: dict[str, tuple[str, str]]

    @property
    def in_sync(self) -> bool:
        return not self.missing and not self.mismatched

    @property
    def difference_count(self) -> int:
        return len(self.missing) + len(self.mismatched)


@dataclass(frozen=True)
class PackagesComparison:
    saved: tuple[PackageRequirement, ...]
    current: tuple[PackageRequirement, ...]
    missing: tuple[PackageRequirement, ...]
    mismatched: tuple[PackageRequirement, ...]

    @property
    def in_sync(self) -> bool:
        return not self.missing and not self.mismatched

    @property
    def difference_count(self) -> int:
        return len(self.missing) + len(self.mismatched)

    def current_version_for(
        self,
        requirement: PackageRequirement,
    ) -> str | None:
        for current in self.current:
            if (
                current.normalized_name
                == requirement.normalized_name
            ):
                return current.version

        return None


@dataclass(frozen=True)
class WSLComparison:
    saved: tuple[WslDistribution, ...]
    current: tuple[WslDistribution, ...]
    missing: tuple[WslDistribution, ...]

    @property
    def in_sync(self) -> bool:
        return not self.missing

    @property
    def difference_count(self) -> int:
        return len(self.missing)


@dataclass(frozen=True)
class EnvironmentVariablesComparison:
    saved: dict[str, str]
    current: dict[str, str]
    missing: tuple[str, ...]
    mismatched: tuple[tuple[str, str, str], ...]
    secrets: tuple[str, ...]

    @property
    def in_sync(self) -> bool:
        return not self.missing and not self.mismatched

    @property
    def difference_count(self) -> int:
        return len(self.missing) + len(self.mismatched)

    @property
    def mismatched_names(self) -> tuple[str, ...]:
        return tuple(
            name for name, _saved, _current in self.mismatched
        )


@dataclass(frozen=True)
class ComparisonReport:
    """Comparison of a saved setup with one environment scan."""

    applications: list[ComparisonItem]
    extensions: ExtensionsComparison
    git_config: GitConfigComparison
    python_packages: PackagesComparison
    npm_packages: PackagesComparison
    wsl: WSLComparison
    environment: EnvironmentVariablesComparison
    terminal: TerminalSettings
    snapshot: EnvironmentSnapshot

    @property
    def missing_applications(self) -> list[ComparisonItem]:
        return [
            item
            for item in self.applications
            if item.status is ComparisonStatus.MISSING
        ]

    @property
    def mismatched_applications(self) -> list[ComparisonItem]:
        return [
            item
            for item in self.applications
            if item.status is ComparisonStatus.VERSION_MISMATCH
        ]

    @property
    def restorable_item_count(self) -> int:
        return (
            len(self.missing_applications)
            + len(self.mismatched_applications)
            + self.extensions.difference_count
            + self.python_packages.difference_count
            + self.npm_packages.difference_count
            + self.git_config.difference_count
            + self.environment.difference_count
            + self.wsl.difference_count
        )

    @property
    def has_restorable_items(self) -> bool:
        return self.restorable_item_count > 0
