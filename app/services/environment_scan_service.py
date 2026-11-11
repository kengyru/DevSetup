from app.models.environment import EnvironmentSnapshot
from app.scanner.base import BaseCollector
from app.scanner.docker import DockerScanner
from app.scanner.environment import EnvironmentScanner
from app.scanner.git import GitScanner
from app.scanner.git_config import GitConfigScanner
from app.scanner.npm_packages import NpmPackagesScanner
from app.scanner.postgresql import PostgreSQLScanner
from app.scanner.python import PythonScanner
from app.scanner.python_packages import PythonPackagesScanner
from app.scanner.terminal import TerminalScanner
from app.scanner.vscode import VSCodeScanner
from app.scanner.vscode_extensions import VSCodeExtensionsScanner
from app.scanner.wsl import WSLScanner
from app.services.scan_service import ScanService


_DEFAULT_VALUES = {
    "vscode_extensions": list,
    "git_config": dict,
    "python_packages": list,
    "npm_packages": list,
    "wsl_distributions": list,
    "environment_variables": dict,
}


def default_application_scanners():
    return [
        PythonScanner(),
        GitScanner(),
        VSCodeScanner(),
        DockerScanner(),
        PostgreSQLScanner(),
    ]


class EnvironmentScanService:
    """Runs the application scanners plus all extra collectors.

    Every collector is isolated: a broken tool never stops the scan, its
    error is reported through `snapshot.errors`.
    """

    def __init__(
        self,
        application_scanners=None,
        collectors: dict[str, BaseCollector] | None = None,
        terminal_scanner: BaseCollector | None = None,
    ):
        self.application_scanners = (
            list(application_scanners)
            if application_scanners is not None
            else default_application_scanners()
        )

        self.collectors = collectors or {
            "vscode_extensions": VSCodeExtensionsScanner(),
            "git_config": GitConfigScanner(),
            "python_packages": PythonPackagesScanner(),
            "npm_packages": NpmPackagesScanner(),
            "wsl_distributions": WSLScanner(),
            "environment_variables": EnvironmentScanner(),
        }

        self.terminal_scanner = (
            terminal_scanner or TerminalScanner()
        )

    def scan(self, report=None) -> EnvironmentSnapshot:
        snapshot = EnvironmentSnapshot()
        errors: list[str] = []

        if report:
            report("Scanning installed applications...")

        scan_service = ScanService(
            scanners=self.application_scanners
        )

        snapshot.applications = scan_service.scan()
        errors.extend(scan_service.errors)

        for attribute, collector in self.collectors.items():
            if report:
                report(f"Scanning {collector.NAME}...")

            try:
                value = collector.scan()

            except Exception as error:
                errors.append(f"{collector.NAME}: {error}")
                value = _DEFAULT_VALUES.get(
                    attribute,
                    list,
                )()

            setattr(snapshot, attribute, value)

        if report:
            report(
                f"Scanning {self.terminal_scanner.NAME}..."
            )

        try:
            snapshot.terminal = self.terminal_scanner.scan()

        except Exception as error:
            errors.append(
                f"{self.terminal_scanner.NAME}: {error}"
            )

        environment_scanner = self.collectors.get(
            "environment_variables"
        )

        if isinstance(
            environment_scanner,
            EnvironmentScanner,
        ):
            snapshot.secret_environment_variables = list(
                environment_scanner.secrets
            )

        else:
            secrets = getattr(
                environment_scanner,
                "secrets",
                None,
            )

            if isinstance(secrets, list):
                snapshot.secret_environment_variables = list(
                    secrets
                )

        snapshot.capabilities = {
            "python": bool(
                getattr(
                    self.collectors.get(
                        "python_packages"
                    ),
                    "available",
                    False,
                )
            ),
            "git": bool(
                getattr(
                    self.collectors.get("git_config"),
                    "available",
                    False,
                )
            ),
            "npm": bool(
                getattr(
                    self.collectors.get("npm_packages"),
                    "available",
                    False,
                )
            ),
            "wsl": bool(
                getattr(
                    self.collectors.get("wsl_distributions"),
                    "available",
                    False,
                )
            ),
            "vscode": bool(
                getattr(
                    self.collectors.get(
                        "vscode_extensions"
                    ),
                    "available",
                    False,
                )
            ),
            "terminal": snapshot.terminal.available,
        }

        snapshot.errors = errors

        return snapshot
