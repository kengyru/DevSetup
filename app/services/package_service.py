"""Restores global Python and npm packages."""

import os
import tempfile

from app.core.process import (
    ProcessTimeoutError,
    run_process,
)
from app.core.requirements import (
    is_valid_npm_name,
    parse_pip_requirement,
    parse_pip_freeze,
)
from app.models.package import PackageRequirement
from app.models.restore import OperationResult
from app.scanner.npm_packages import find_npm
from app.scanner.python_packages import find_global_python

_PIP_TIMEOUT = 1800
_NPM_TIMEOUT = 600


def _npm_command(npm_path: str, arguments: list[str]) -> list[str]:
    if os.name == "nt" and npm_path.lower().endswith(
        (".cmd", ".bat")
    ):
        return ["cmd", "/c", npm_path, *arguments]

    return [npm_path, *arguments]


class PackageService:
    """Installs Python requirements and npm global packages.

    Python packages are installed in one pip run from a temporary
    requirements file. npm packages are installed one by one so a single
    broken package does not hide the others.
    """

    def __init__(
        self,
        python_path: str | None = None,
        npm_path: str | None = None,
    ):
        self._python_path = python_path
        self._npm_path = npm_path

    def find_python(self) -> str | None:
        if self._python_path:
            return self._python_path

        return find_global_python()

    def find_npm(self) -> str | None:
        if self._npm_path:
            return self._npm_path

        return find_npm()

    def install_python(
        self,
        entries: list[str],
    ) -> list[OperationResult]:
        slots: list[OperationResult | None] = [
            None
        ] * len(entries)
        valid: list[tuple[int, PackageRequirement]] = []

        for index, entry in enumerate(entries):
            requirement = parse_pip_requirement(entry)

            if requirement is None:
                slots[index] = OperationResult(
                    name=entry,
                    success=False,
                    message=(
                        "Unsafe or invalid Python requirement. "
                        "Only 'name==version' is allowed."
                    ),
                )
                continue

            valid.append((index, requirement))

        if not valid:
            return [
                slot
                for slot in slots
                if slot is not None
            ]

        def fill(success: bool, message: str) -> list[OperationResult]:
            for index, requirement in valid:
                slots[index] = OperationResult(
                    name=requirement.raw,
                    success=success,
                    message=message,
                )

            return [
                slot
                for slot in slots
                if slot is not None
            ]

        requirements = [
            requirement for _index, requirement in valid
        ]

        python_path = self.find_python()

        if not python_path:
            return fill(False, "Python is not installed.")

        requirements_path = None

        try:
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                prefix="devsetup-requirements-",
                delete=False,
                encoding="utf-8",
            )

            with handle:
                for requirement in requirements:
                    handle.write(f"{requirement.raw}\n")

            requirements_path = handle.name

            result = run_process(
                [
                    python_path,
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--disable-pip-version-check",
                    "-r",
                    requirements_path,
                ],
                timeout=_PIP_TIMEOUT,
            )

        except ProcessTimeoutError:
            return fill(
                False,
                "pip did not finish in time. Some packages may have "
                "been installed; run the scan again to check.",
            )

        except OSError as error:
            return fill(False, f"Could not run pip: {error}")

        finally:
            if requirements_path:
                try:
                    os.unlink(requirements_path)
                except OSError:
                    pass

        if result.success:
            return fill(True, "Installed.")

        return fill(
            False,
            result.output[:1500]
            or f"pip exited with code {result.returncode}.",
        )

    def install_npm(
        self,
        names: list[str],
    ) -> list[OperationResult]:
        slots: list[OperationResult | None] = [
            None
        ] * len(names)
        valid: list[tuple[int, str]] = []

        for index, name in enumerate(names):
            if not is_valid_npm_name(name):
                slots[index] = OperationResult(
                    name=name,
                    success=False,
                    message="Invalid npm package name.",
                )
                continue

            valid.append((index, name))

        if not valid:
            return [
                slot
                for slot in slots
                if slot is not None
            ]

        npm_path = self.find_npm()

        if not npm_path:
            for index, name in valid:
                slots[index] = OperationResult(
                    name=name,
                    success=False,
                    message="npm is not installed.",
                )

            return [
                slot
                for slot in slots
                if slot is not None
            ]

        for index, name in valid:
            try:
                result = run_process(
                    _npm_command(
                        npm_path,
                        [
                            "install",
                            "-g",
                            name,
                            "--no-fund",
                            "--no-audit",
                        ],
                    ),
                    timeout=_NPM_TIMEOUT,
                )

            except ProcessTimeoutError:
                slots[index] = OperationResult(
                    name=name,
                    success=False,
                    message=(
                        f"npm did not finish installing {name} "
                        "in time."
                    ),
                )
                continue

            except OSError as error:
                slots[index] = OperationResult(
                    name=name,
                    success=False,
                    message=f"Could not run npm: {error}",
                )
                continue

            if result.success:
                slots[index] = OperationResult(
                    name=name,
                    success=True,
                    message="Installed.",
                )
                continue

            slots[index] = OperationResult(
                name=name,
                success=False,
                message=(
                    result.output[:1500]
                    or f"npm exited with code "
                    f"{result.returncode}."
                ),
            )

        return [
            slot
            for slot in slots
            if slot is not None
        ]


def parse_python_package_list(
    lines: list[str],
) -> list[str]:
    """Expose the safe pip parser for callers that only need strings."""

    return [
        requirement.raw
        for requirement in parse_pip_freeze(lines)
    ]
