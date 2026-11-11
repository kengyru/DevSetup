from dataclasses import dataclass, field

from app.models.application import InstalledApplication
from app.models.environment import WslDistribution


@dataclass(frozen=True)
class VersionRestoreItem:
    """A version mismatch the user explicitly chose to restore."""

    application: InstalledApplication
    version: str

    @property
    def name(self) -> str:
        return self.application.name


@dataclass
class RestoreSelection:
    """Everything the user ticked in the restore dialog."""

    applications: list[InstalledApplication] = field(
        default_factory=list
    )
    version_restores: list[VersionRestoreItem] = field(
        default_factory=list
    )
    extensions: list[str] = field(default_factory=list)
    python_packages: list[str] = field(default_factory=list)
    npm_packages: list[str] = field(default_factory=list)
    git_config: dict[str, str] = field(default_factory=dict)
    environment_variables: dict[str, str] = field(
        default_factory=dict
    )
    wsl_distributions: list[WslDistribution] = field(
        default_factory=list
    )

    @property
    def step_count(self) -> int:
        return (
            len(self.applications)
            + len(self.version_restores)
            + len(self.extensions)
            + len(self.python_packages)
            + len(self.npm_packages)
            + len(self.git_config)
            + len(self.environment_variables)
            + len(self.wsl_distributions)
        )

    @property
    def is_empty(self) -> bool:
        return self.step_count == 0

    @property
    def category_count(self) -> int:
        categories = (
            bool(self.applications),
            bool(self.version_restores),
            bool(self.extensions),
            bool(self.python_packages),
            bool(self.npm_packages),
            bool(self.git_config),
            bool(self.environment_variables),
            bool(self.wsl_distributions),
        )

        return sum(1 for category in categories if category)


@dataclass(frozen=True)
class OperationResult:
    """Outcome of one restore operation produced by a single service."""

    name: str
    success: bool
    message: str


@dataclass(frozen=True)
class RestoreStepResult:
    """Outcome of one restore step, grouped by category for the UI."""

    category: str
    name: str
    success: bool
    message: str

    @property
    def label(self) -> str:
        return f"{self.category}: {self.name}"


@dataclass
class RestoreResult:
    results: list[RestoreStepResult] = field(default_factory=list)

    @property
    def succeeded(self) -> list[RestoreStepResult]:
        return [result for result in self.results if result.success]

    @property
    def failed(self) -> list[RestoreStepResult]:
        return [
            result for result in self.results if not result.success
        ]

    @property
    def has_failures(self) -> bool:
        return bool(self.failed)

    @property
    def total(self) -> int:
        return len(self.results)
