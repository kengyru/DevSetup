import os
import shutil
import sys
from pathlib import Path

from app.core.process import ProcessTimeoutError, run_process
from app.core.requirements import parse_pip_freeze
from app.scanner.base import BaseCollector
from app.scanner.command import ScannerError

_PYTHON_INFO_SCRIPT = (
    "import sys; "
    "print(sys.prefix); "
    "print(sys.base_prefix)"
)


def _read_prefixes(python_path: str) -> tuple[str, str] | None:
    try:
        result = run_process(
            [python_path, "-c", _PYTHON_INFO_SCRIPT],
            timeout=15,
        )

    except (OSError, ProcessTimeoutError):
        return None

    lines = [
        line.strip()
        for line in result.output.splitlines()
        if line.strip()
    ]

    if result.returncode != 0 or len(lines) < 2:
        return None

    return lines[0], lines[1]


def _resolve_global(python_path: str) -> str | None:
    """Return the global interpreter behind a possibly virtual one."""

    prefixes = _read_prefixes(python_path)

    if prefixes is None:
        return None

    prefix, base_prefix = prefixes

    if prefix == base_prefix:
        return python_path

    base_python = Path(base_prefix) / "python.exe"

    if base_python.exists():
        return str(base_python)

    return None


def _candidate_python_paths() -> list[Path]:
    candidates: list[Path] = []

    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        candidates.extend(
            sorted(
                Path(local_app_data)
                .joinpath("Programs", "Python")
                .glob("Python3*/python.exe"),
                reverse=True,
            )
        )

    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)

        if base:
            candidates.extend(
                sorted(
                    Path(base).glob("Python3*/python.exe"),
                    reverse=True,
                )
            )

    return candidates


def find_global_python() -> str | None:
    """Find a Python interpreter that is not inside a virtualenv."""

    candidates = []

    for variable in ("python", "python3"):
        found = shutil.which(variable)

        if found:
            candidates.append(found)
            break

    candidates.append(sys.executable)

    for candidate in candidates:
        if not candidate:
            continue

        resolved = _resolve_global(candidate)

        if resolved:
            return resolved

    for candidate in _candidate_python_paths():
        return str(candidate)

    return None


class PythonPackagesScanner(BaseCollector):
    """Reads globally installed Python packages with `pip freeze`."""

    NAME = "Python packages"

    def __init__(self):
        super().__init__()
        self.python_path: str | None = None

    def scan(self) -> list[str]:
        python_path = find_global_python()

        if not python_path:
            self.available = False
            self.python_path = None
            return []

        self.python_path = python_path

        result = run_process(
            [python_path, "-m", "pip", "freeze"],
            timeout=120,
        )

        if result.returncode != 0:
            raise ScannerError(
                result.output or "pip freeze failed."
            )

        requirements = parse_pip_freeze(
            result.output.splitlines()
        )

        return [requirement.raw for requirement in requirements]
