from dataclasses import dataclass, field

from app.models.application import InstalledApplication
from app.models.environment import (
    EnvironmentSnapshot,
    TerminalSettings,
    WslDistribution,
)


@dataclass
class Setup:
    name: str
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
    format_version: int = 1

    @classmethod
    def from_snapshot(
        cls,
        name: str,
        snapshot: EnvironmentSnapshot,
    ) -> "Setup":
        return cls(
            name=name,
            applications=list(snapshot.applications),
            vscode_extensions=list(
                snapshot.vscode_extensions
            ),
            git_config=dict(snapshot.git_config),
            python_packages=list(snapshot.python_packages),
            npm_packages=list(snapshot.npm_packages),
            wsl_distributions=list(
                snapshot.wsl_distributions
            ),
            environment_variables=dict(
                snapshot.environment_variables
            ),
            secret_environment_variables=list(
                snapshot.secret_environment_variables
            ),
            terminal=snapshot.terminal,
            format_version=2,
        )
