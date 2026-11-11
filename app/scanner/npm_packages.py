import json
import os
import re
import shutil
from pathlib import Path

from app.core.process import ProcessTimeoutError, run_process
from app.core.requirements import is_valid_npm_name
from app.scanner.base import BaseCollector
from app.scanner.command import ScannerError

_DEPENDENCY_LINE_RE = re.compile(
    r"(?P<name>@?[A-Za-z0-9][A-Za-z0-9._/-]*)@[^\s]+"
)


def _candidate_npm_paths() -> list[Path]:
    candidates: list[Path] = []

    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)

        if base:
            candidates.append(
                Path(base) / "nodejs" / "npm.cmd"
            )

    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Programs" / "nodejs" / "npm.cmd"
        )

    return candidates


def find_npm() -> str | None:
    npm_path = shutil.which("npm")

    if npm_path:
        return npm_path

    for candidate in _candidate_npm_paths():
        if candidate.exists():
            return str(candidate)

    return None


def parse_npm_output(output: str) -> list[str]:
    """Parse `npm list -g --depth=0 --json` or its text output."""

    if not output.strip():
        return []

    try:
        data = json.loads(output)

    except json.JSONDecodeError:
        data = None

    packages: set[str] = set()

    if isinstance(data, dict):
        dependencies = data.get("dependencies")

        if isinstance(dependencies, dict):
            for name in dependencies:
                if is_valid_npm_name(name):
                    packages.add(name)

            return sorted(packages)

    for line in output.splitlines():
        match = _DEPENDENCY_LINE_RE.search(line)

        if not match:
            continue

        name = match.group("name")

        if is_valid_npm_name(name):
            packages.add(name)

    return sorted(packages)


class NpmPackagesScanner(BaseCollector):
    """Reads globally installed npm packages."""

    NAME = "npm global packages"

    def __init__(self):
        super().__init__()
        self.npm_path: str | None = None

    def scan(self) -> list[str]:
        npm_path = find_npm()

        if not npm_path:
            self.available = False
            self.npm_path = None
            return []

        self.npm_path = npm_path

        try:
            result = run_process(
                [
                    npm_path,
                    "list",
                    "-g",
                    "--depth=0",
                    "--json",
                ],
                timeout=120,
            )

        except ProcessTimeoutError as error:
            raise ScannerError(str(error)) from error

        packages = parse_npm_output(result.output)

        if result.returncode != 0 and not packages:
            raise ScannerError(
                result.output or "npm list failed."
            )

        return packages
