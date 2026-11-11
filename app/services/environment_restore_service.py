"""Coordinates every restore step selected by the user."""

from app.models.restore import (
    OperationResult,
    RestoreResult,
    RestoreSelection,
    RestoreStepResult,
)
from app.services.config_service import (
    EnvironmentVariableService,
    GitConfigService,
)
from app.services.extension_service import ExtensionService
from app.services.package_service import PackageService
from app.services.restore_service import RestoreService
from app.services.wsl_service import WSLService


class EnvironmentRestoreService:
    """Runs only what the user explicitly selected.

    Every service returns per-item results instead of raising, so one
    broken tool does not hide the rest of the restore. Long external
    commands are executed here, outside the GUI thread.
    """

    def __init__(
        self,
        restore_service: RestoreService | None = None,
        extension_service: ExtensionService | None = None,
        package_service: PackageService | None = None,
        git_config_service: GitConfigService | None = None,
        environment_service: EnvironmentVariableService | None = None,
        wsl_service: WSLService | None = None,
    ):
        self.restore_service = restore_service or RestoreService()
        self.extension_service = (
            extension_service or ExtensionService()
        )
        self.package_service = package_service or PackageService()
        self.git_config_service = (
            git_config_service or GitConfigService()
        )
        self.environment_service = (
            environment_service or EnvironmentVariableService()
        )
        self.wsl_service = wsl_service or WSLService()

    def run(
        self,
        selection: RestoreSelection,
        reporter=None,
    ) -> RestoreResult:
        result = RestoreResult()
        total = selection.step_count
        done = 0

        def status(text: str) -> None:
            if reporter is not None:
                reporter.set_text(text)

        def tick() -> None:
            nonlocal done
            done += 1

            if reporter is not None:
                reporter.set_progress(done, total)

        def add(
            category: str,
            items: list[OperationResult],
        ) -> None:
            for item in items:
                result.results.append(
                    RestoreStepResult(
                        category=category,
                        name=item.name,
                        success=item.success,
                        message=item.message,
                    )
                )
                tick()

        # Applications first so VS Code exists before extensions are
        # installed.
        for application in selection.applications:
            status(f"Installing {application.name}...")

            success, message = self.restore_service.install(
                application
            )

            add(
                "Application",
                [
                    OperationResult(
                        name=application.name,
                        success=success,
                        message=message,
                    )
                ],
            )

        for version_item in selection.version_restores:
            status(
                f"Restoring {version_item.name} "
                f"{version_item.version}..."
            )

            success, message = self.restore_service.install_version(
                version_item.application,
                version_item.version,
            )

            add(
                "Application version",
                [
                    OperationResult(
                        name=(
                            f"{version_item.name} "
                            f"{version_item.version}"
                        ),
                        success=success,
                        message=message,
                    )
                ],
            )

        if selection.extensions:
            total_extensions = len(selection.extensions)

            for index, extension_id in enumerate(
                selection.extensions,
                start=1,
            ):
                status(
                    "Installing VS Code extensions "
                    f"({index}/{total_extensions})..."
                )

                success, message = self.extension_service.install(
                    extension_id
                )

                add(
                    "VS Code extension",
                    [
                        OperationResult(
                            name=extension_id,
                            success=success,
                            message=message,
                        )
                    ],
                )

        if selection.python_packages:
            status("Restoring Python packages...")

            add(
                "Python package",
                self.package_service.install_python(
                    selection.python_packages
                ),
            )

        if selection.npm_packages:
            for name in selection.npm_packages:
                status(f"Installing npm package {name}...")

                add(
                    "npm package",
                    self.package_service.install_npm([name]),
                )

        if selection.git_config:
            status("Restoring Git configuration...")

            add(
                "Git config",
                self.git_config_service.apply(
                    selection.git_config
                ),
            )

        if selection.environment_variables:
            status("Restoring environment variables...")

            add(
                "Environment variable",
                self.environment_service.apply(
                    selection.environment_variables
                ),
            )

        for distribution in selection.wsl_distributions:
            status(
                f"Installing WSL distribution "
                f"{distribution.name}..."
            )

            add(
                "WSL",
                [self.wsl_service.install(distribution)],
            )

        if reporter is not None:
            reporter.set_progress(done, total)

        return result
