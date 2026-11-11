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
from app.models.application import InstalledApplication
from app.models.environment import (
    TerminalSettings,
    WslDistribution,
)
from app.models.setup import Setup
from app.scanner.git_config import get_safe_git_settings

_MAX_ENVIRONMENT_VALUE_LENGTH = 4000


class SetupImporter:
    """Reads and validates a .setup file.

    Format versions 1 and 2 are accepted. A missing ``format_version`` is
    treated as version 1, so setup files created by the first MVP keep
    working. Everything that comes out of the file is treated as untrusted
    input: unsafe package entries, Git settings and environment variables
    are dropped instead of being passed to a shell.
    """

    SUPPORTED_FORMAT_VERSIONS = (1, 2)

    def import_setup(self, file_path: str) -> Setup:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Setup file not found: {file_path}"
            )

        if path.is_dir():
            raise ValueError(
                f"'{file_path}' is a folder, not a setup file."
            )

        try:
            raw_text = path.read_text(encoding="utf-8")

        except UnicodeDecodeError as error:
            raise ValueError(
                "The setup file is not valid UTF-8 text."
            ) from error

        except OSError as error:
            raise OSError(
                f"Could not read '{file_path}': {error}"
            ) from error

        try:
            data = json.loads(raw_text)

        except json.JSONDecodeError as error:
            raise ValueError(
                "The setup file is not valid JSON: "
                f"{error.msg} "
                f"(line {error.lineno}, column {error.colno})."
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "The setup file must contain a JSON object."
            )

        format_version = data.get("format_version", 1)

        if isinstance(format_version, bool) or not isinstance(
            format_version, int
        ):
            raise ValueError(
                "The 'format_version' field must be an integer."
            )

        if format_version not in self.SUPPORTED_FORMAT_VERSIONS:
            raise ValueError(
                "Unsupported setup format version: "
                f"{format_version!r}."
            )

        raw_applications = data.get("applications", [])

        if not isinstance(raw_applications, list):
            raise ValueError(
                "The 'applications' field must be a list."
            )

        applications = [
            InstalledApplication.from_dict(item)
            for item in raw_applications
        ]

        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            name = "Unnamed Setup"

        environment_variables, secret_variables = (
            self._import_environment(data)
        )

        return Setup(
            name=name.strip(),
            applications=applications,
            vscode_extensions=self._import_extensions(
                data,
                raw_applications,
            ),
            git_config=self._import_git_config(
                data.get("git_config", {})
            ),
            python_packages=self._import_python_packages(
                data.get("python_packages", [])
            ),
            npm_packages=self._import_npm_packages(
                data.get("npm_packages", [])
            ),
            wsl_distributions=self._import_wsl(
                data.get("wsl_distributions", [])
            ),
            environment_variables=environment_variables,
            secret_environment_variables=secret_variables,
            terminal=self._import_terminal(
                data.get("terminal")
            ),
            format_version=format_version,
        )

    def _import_extensions(
        self,
        data: dict,
        raw_applications: list,
    ) -> list[str]:
        entries: list = []

        raw_top = data.get("vscode_extensions", [])

        if raw_top is None:
            raw_top = []

        if not isinstance(raw_top, list):
            raise ValueError(
                "The 'vscode_extensions' field must be a list."
            )

        entries.extend(raw_top)

        for item in raw_applications:
            if not isinstance(item, dict):
                continue

            name = item.get("name")

            if not isinstance(name, str):
                continue

            if name.strip().lower() != "vs code":
                continue

            raw_entry = item.get("extensions", [])

            if raw_entry is None:
                continue

            if not isinstance(raw_entry, list):
                raise ValueError(
                    "The 'extensions' field of VS Code must be "
                    "a list."
                )

            entries.extend(raw_entry)

        result = []
        seen = set()

        for extension_id in entries:
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

    def _import_git_config(self, raw: object) -> dict[str, str]:
        if raw is None:
            return {}

        if not isinstance(raw, dict):
            raise ValueError(
                "The 'git_config' field must be a JSON object."
            )

        settings = {
            key: value
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, str)
        }

        return get_safe_git_settings(settings)

    def _import_python_packages(
        self,
        raw: object,
    ) -> list[str]:
        if raw is None:
            return []

        if not isinstance(raw, list):
            raise ValueError(
                "The 'python_packages' field must be a list."
            )

        result = []
        seen = set()

        for entry in raw:
            if not isinstance(entry, str):
                continue

            requirement = parse_pip_requirement(entry)

            if requirement is None:
                continue

            if requirement.normalized_name in seen:
                continue

            seen.add(requirement.normalized_name)
            result.append(requirement.raw)

        return result

    def _import_npm_packages(self, raw: object) -> list[str]:
        if raw is None:
            return []

        if not isinstance(raw, list):
            raise ValueError(
                "The 'npm_packages' field must be a list."
            )

        result = []
        seen = set()

        for entry in raw:
            if not isinstance(entry, str):
                continue

            name = entry.strip()

            if not is_valid_npm_name(name):
                continue

            key = name.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(name)

        return result

    def _import_wsl(
        self,
        raw: object,
    ) -> list[WslDistribution]:
        if raw is None:
            return []

        if not isinstance(raw, list):
            raise ValueError(
                "The 'wsl_distributions' field must be a list."
            )

        result = []
        seen = set()

        for entry in raw:
            try:
                distribution = WslDistribution.from_dict(entry)

            except ValueError:
                continue

            key = distribution.name.lower()

            if key in seen:
                continue

            if not is_valid_wsl_name(distribution.name):
                continue

            seen.add(key)
            result.append(distribution)

        return result

    def _import_environment(
        self,
        data: dict,
    ) -> tuple[dict[str, str], list[str]]:
        raw = data.get("environment_variables", {})

        if raw is None:
            raw = {}

        if not isinstance(raw, dict):
            raise ValueError(
                "The 'environment_variables' field must be "
                "a JSON object."
            )

        saved: dict[str, str] = {}
        secrets: set[str] = set()

        for name, value in raw.items():
            if not isinstance(name, str) or not isinstance(
                value, str
            ):
                continue

            if is_secret_name(name):
                secrets.add(name)
                continue

            if not is_safe_environment_name(name):
                continue

            if (
                len(value) > _MAX_ENVIRONMENT_VALUE_LENGTH
                or "\x00" in value
            ):
                continue

            saved[name] = value

        raw_secrets = data.get(
            "secret_environment_variables",
            [],
        )

        if raw_secrets is None:
            raw_secrets = []

        if not isinstance(raw_secrets, list):
            raise ValueError(
                "The 'secret_environment_variables' field must "
                "be a list."
            )

        for name in raw_secrets:
            if isinstance(name, str) and name.strip():
                secrets.add(name.strip())

        return dict(sorted(saved.items())), sorted(secrets)

    def _import_terminal(
        self,
        raw: object,
    ) -> TerminalSettings:
        if raw is None:
            return TerminalSettings()

        return TerminalSettings.from_dict(raw)
