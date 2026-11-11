"""Shared helper for running external commands used by restore services."""

import os
import subprocess
from dataclasses import dataclass

_CREATE_NO_WINDOW = 0x08000000

_DEFAULT_ENCODING = "utf-8"


class ProcessTimeoutError(RuntimeError):
    """Raised when a command does not finish within its timeout."""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    output: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


def run_process(
    command: list[str],
    timeout: int,
    encoding: str = _DEFAULT_ENCODING,
) -> ProcessResult:
    """Run a command without a shell and return its combined output."""

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
            creationflags=(
                _CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )

    except subprocess.TimeoutExpired as error:
        raise ProcessTimeoutError(
            f"'{command[0]}' did not finish within "
            f"{timeout} seconds."
        ) from error

    except OSError as error:
        raise OSError(
            f"Could not start '{command[0]}': {error}"
        ) from error

    output = (result.stdout or "").strip()

    if not output:
        output = (result.stderr or "").strip()

    return ProcessResult(
        returncode=result.returncode,
        output=output,
    )
