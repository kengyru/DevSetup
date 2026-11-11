"""Small helper for asking command line tools for their version."""

import os
import subprocess

DEFAULT_TIMEOUT = 15

_CREATE_NO_WINDOW = 0x08000000


class ScannerError(RuntimeError):
    """Raised when a scanner cannot read information from an external tool."""


def run_command(
    path: str,
    arguments: list[str],
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Run a tool and return its output.

    Never raises subprocess exceptions: callers only need to handle
    ScannerError. A timeout is always applied so a hung tool cannot freeze
    the application.
    """

    if os.name == "nt" and path.lower().endswith((".cmd", ".bat")):
        command = ["cmd", "/c", path, *arguments]
    else:
        command = [path, *arguments]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=(
                _CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )

    except subprocess.TimeoutExpired as error:
        raise ScannerError(
            f"'{path}' did not answer within {timeout} seconds."
        ) from error

    except OSError as error:
        raise ScannerError(
            f"Could not run '{path}': {error}"
        ) from error

    output = (result.stdout or "").strip()

    if not output:
        output = (result.stderr or "").strip()

    if result.returncode != 0:
        raise ScannerError(
            output or f"'{path}' exited with code {result.returncode}."
        )

    if not output:
        raise ScannerError(f"'{path}' returned no output.")

    return output
