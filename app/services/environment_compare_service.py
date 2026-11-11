from app.core.requirements import (
    is_valid_npm_name,
    normalize_package_name,
    parse_pip_requirement,
)
from app.core.secrets import is_safe_environment_name
from app.models.comparison import (
    ComparisonReport,
    EnvironmentVariablesComparison,
    ExtensionsComparison,
    GitConfigComparison,
    PackagesComparison,
    WSLComparison,
)
from app.models.environment import EnvironmentSnapshot
from app.models.package import PackageRequirement
from app.models.setup import Setup
from app.scanner.git_config import get_safe_git_settings
from app.services.compare_service import CompareService


def _parse_requirements(
    entries: list[str],
) -> tuple[PackageRequirement, ...]:
    requirements = []

    for entry in entries:
        requirement = parse_pip_requirement(entry)

        if requirement is not None:
            requirements.append(requirement)

    return tuple(requirements)


def _unique(values: list[str]) -> tuple[str, ...]:
    result = []
    seen = set()

    for value in values:
        if not value:
            continue

        key = value.strip().lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(value.strip())

    return tuple(result)


class EnvironmentCompareService:
    """Compares a saved setup with one environment scan."""

    def __init__(self, compare_service: CompareService | None = None):
        self.compare_service = compare_service or CompareService()

    def compare(
        self,
        setup: Setup,
        snapshot: EnvironmentSnapshot,
    ) -> ComparisonReport:

        applications = self.compare_service.compare(
            saved_applications=setup.applications,
            current_applications=snapshot.applications,
        )

        extensions = self.compare_extensions(
            setup.vscode_extensions,
            snapshot.vscode_extensions,
        )

        git_config = self.compare_git_config(
            setup.git_config,
            snapshot.git_config,
        )

        python_packages = self.compare_packages(
            setup.python_packages,
            snapshot.python_packages,
        )

        npm_packages = self.compare_npm_packages(
            setup.npm_packages,
            snapshot.npm_packages,
        )

        wsl = self.compare_wsl(
            setup.wsl_distributions,
            snapshot.wsl_distributions,
        )

        environment = self.compare_environment(
            setup.environment_variables,
            snapshot.environment_variables,
            snapshot.secret_environment_variables,
        )

        return ComparisonReport(
            applications=applications,
            extensions=extensions,
            git_config=git_config,
            python_packages=python_packages,
            npm_packages=npm_packages,
            wsl=wsl,
            environment=environment,
            terminal=snapshot.terminal,
            snapshot=snapshot,
        )

    def compare_extensions(
        self,
        saved: list[str],
        current: list[str],
    ) -> ExtensionsComparison:
        saved_items = _unique(saved)
        current_items = _unique(current)

        current_keys = {
            item.lower() for item in current_items
        }

        missing = tuple(
            item
            for item in saved_items
            if item.lower() not in current_keys
        )

        return ExtensionsComparison(
            saved=saved_items,
            current=current_items,
            missing=missing,
        )

    def compare_git_config(
        self,
        saved: dict[str, str],
        current: dict[str, str],
    ) -> GitConfigComparison:
        saved_settings = get_safe_git_settings(saved)
        current_settings = get_safe_git_settings(current)

        missing = {
            key: value
            for key, value in saved_settings.items()
            if key not in current_settings
        }

        mismatched = {
            key: (value, current_settings[key])
            for key, value in saved_settings.items()
            if key in current_settings
            and current_settings[key] != value
        }

        return GitConfigComparison(
            saved=saved_settings,
            current=current_settings,
            missing=missing,
            mismatched=mismatched,
        )

    def compare_packages(
        self,
        saved: list[str],
        current: list[str],
    ) -> PackagesComparison:
        saved_requirements = _parse_requirements(saved)
        current_requirements = _parse_requirements(current)

        current_by_name = {
            requirement.normalized_name: requirement
            for requirement in current_requirements
        }

        missing = []
        mismatched = []

        for requirement in saved_requirements:
            installed = current_by_name.get(
                requirement.normalized_name
            )

            if installed is None:
                missing.append(requirement)

            elif installed.version != requirement.version:
                mismatched.append(requirement)

        return PackagesComparison(
            saved=saved_requirements,
            current=current_requirements,
            missing=tuple(missing),
            mismatched=tuple(mismatched),
        )

    def compare_npm_packages(
        self,
        saved: list[str],
        current: list[str],
    ) -> PackagesComparison:
        saved_requirements = tuple(
            PackageRequirement(
                name=name,
                version=None,
                raw=name,
            )
            for name in _unique(saved)
            if is_valid_npm_name(name)
        )

        current_requirements = tuple(
            PackageRequirement(
                name=name,
                version=None,
                raw=name,
            )
            for name in _unique(current)
            if is_valid_npm_name(name)
        )

        current_names = {
            normalize_package_name(requirement.name)
            for requirement in current_requirements
        }

        missing = tuple(
            requirement
            for requirement in saved_requirements
            if normalize_package_name(requirement.name)
            not in current_names
        )

        return PackagesComparison(
            saved=saved_requirements,
            current=current_requirements,
            missing=missing,
            mismatched=(),
        )

    def compare_wsl(
        self,
        saved,
        current,
    ) -> WSLComparison:
        current_names = {
            distribution.name.lower()
            for distribution in current
        }

        missing = tuple(
            distribution
            for distribution in saved
            if distribution.name.lower() not in current_names
        )

        return WSLComparison(
            saved=tuple(saved),
            current=tuple(current),
            missing=missing,
        )

    def compare_environment(
        self,
        saved: dict[str, str],
        current: dict[str, str],
        secrets: list[str],
    ) -> EnvironmentVariablesComparison:
        saved_variables = {
            name: value
            for name, value in saved.items()
            if is_safe_environment_name(name)
            and isinstance(value, str)
        }

        current_variables = {
            name: value
            for name, value in current.items()
            if is_safe_environment_name(name)
            and isinstance(value, str)
        }

        missing = tuple(
            name
            for name in saved_variables
            if name not in current_variables
        )

        mismatched = tuple(
            (
                name,
                value,
                current_variables[name],
            )
            for name, value in saved_variables.items()
            if name in current_variables
            and current_variables[name] != value
        )

        return EnvironmentVariablesComparison(
            saved=saved_variables,
            current=current_variables,
            missing=missing,
            mismatched=mismatched,
            secrets=tuple(sorted(set(secrets))),
        )
