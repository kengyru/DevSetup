import json
from pathlib import Path

from app.core.requirements import (
    is_valid_extension_id,
    is_valid_npm_name,
    is_valid_wsl_name,
    parse_pip_requirement,
)
from app.core.secrets import (
    is_safe_environment_name,
    is_secret_name,
)
from app.models.setup import Setup
from app.scanner.git_config import get_safe_git_settings

_MAX_ENVIRONMENT_VALUE_LENGTH = 4000


def _safe_extensions(extensions: list[str]) -> list[str]:
    result = []
    seen = set()

    for extension_id in extensions:
        if not isinstance(extension_id, str):
            continue

        extension_id = extension_id.strip()
        key = extension_id.lower()

        if not is_valid_extension_id(extension_id):
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(extension_id)

    return sorted(result)


def _safe_python_packages(packages: list[str]) -> list[str]:
    result = []
    seen = set()

    for entry in packages:
        requirement = parse_pip_requirement(entry)

        if requirement is None:
            continue

        if requirement.normalized_name in seen:
            continue

        seen.add(requirement.normalized_name)
        result.append(requirement.raw)

    return result


def _safe_npm_packages(packages: list[str]) -> list[str]:
    result = []
    seen = set()

    for name in packages:
        if not isinstance(name, str):
            continue

        name = name.strip()

        if not is_valid_npm_name(name):
            continue

        key = name.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(name)

    return result


def _safe_environment(
    variables: dict[str, str],
    known_secrets: list[str],
) -> tuple[dict[str, str], list[str]]:
    safe: dict[str, str] = {}
    secrets = {
        name
        for name in known_secrets
        if isinstance(name, str) and name
    }

    for name, value in variables.items():
        if not isinstance(name, str):
            continue

        if is_secret_name(name):
            secrets.add(name)
            continue

        if not is_safe_environment_name(name):
            continue

        if not isinstance(value, str):
            continue

        if (
            len(value) > _MAX_ENVIRONMENT_VALUE_LENGTH
            or "\x00" in value
        ):
            continue

        safe[name] = value

    return dict(sorted(safe.items())), sorted(secrets)


class SetupExporter:
    """Writes a setup to a plain JSON .setup file (format version 2)."""

    FORMAT_VERSION = 2

    def export(
        self,
        setup: Setup,
        output_path: str,
    ) -> Path:
        path = Path(output_path)

        applications = []
        extensions = _safe_extensions(
            setup.vscode_extensions
        )
        extensions_written = False

        for application in setup.applications:
            entry = application.to_dict()

            if (
                application.name.strip().lower() == "vs code"
                and extensions
            ):
                entry["extensions"] = list(extensions)
                extensions_written = True

            applications.append(entry)

        environment_variables, secret_variables = (
            _safe_environment(
                setup.environment_variables,
                setup.secret_environment_variables,
            )
        )

        data = {
            "format_version": self.FORMAT_VERSION,
            "name": setup.name,
            "applications": applications,
            "git_config": get_safe_git_settings(
                setup.git_config
            ),
            "python_packages": _safe_python_packages(
                setup.python_packages
            ),
            "npm_packages": _safe_npm_packages(
                setup.npm_packages
            ),
            "wsl_distributions": [
                distribution.to_dict()
                for distribution in setup.wsl_distributions
                if is_valid_wsl_name(distribution.name)
            ],
            "environment_variables": environment_variables,
            "secret_environment_variables": secret_variables,
            "terminal": setup.terminal.to_dict(),
        }

        if extensions and not extensions_written:
            # v1-style setups have no VS Code entry, so keep the
            # extensions at the top level instead of losing them.
            data["vscode_extensions"] = list(extensions)

        try:
            path.write_text(
                json.dumps(
                    data,
                    indent=4,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

        except OSError as error:
            raise OSError(
                f"Could not write '{path}': {error}"
            ) from error

        return path
