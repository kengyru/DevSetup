import os
import shutil
import subprocess

from app.models.environment import WslDistribution
from app.scanner.base import BaseCollector
from app.scanner.command import ScannerError

_CREATE_NO_WINDOW = 0x08000000


def decode_wsl_output(data: bytes) -> str:
    """Decode wsl.exe output, which is UTF-16LE when redirected."""

    if not data:
        return ""

    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16", errors="replace")

    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")

    if data.count(b"\x00") > max(1, len(data) // 4):
        return data.decode("utf-16-le", errors="replace")

    return data.decode("utf-8", errors="replace")


def parse_wsl_list(text: str) -> list[WslDistribution]:
    """Parse `wsl --list --verbose`.

    The header is localized, so it is skipped by checking that the last
    token is a WSL version number.
    """

    distributions = []

    for raw_line in text.splitlines():
        line = raw_line.replace("\x00", "").strip()

        if not line:
            continue

        if line.startswith("*"):
            line = line[1:].strip()

        parts = line.split()

        if len(parts) < 3:
            continue

        try:
            version = int(parts[-1])

        except ValueError:
            continue

        if version not in (1, 2):
            continue

        name = parts[0]
        state = " ".join(parts[1:-1]) or None

        distributions.append(
            WslDistribution(
                name=name,
                version=version,
                state=state,
            )
        )

    return distributions


def _run_wsl(args: list[str], timeout: int):
    return subprocess.run(
        ["wsl", *args],
        capture_output=True,
        timeout=timeout,
        creationflags=(
            _CREATE_NO_WINDOW if os.name == "nt" else 0
        ),
    )


class WSLScanner(BaseCollector):
    """Detects WSL distributions without touching the Linux filesystem."""

    NAME = "WSL distributions"

    def __init__(self):
        super().__init__()
        self.status_text = ""

    def scan(self) -> list[WslDistribution]:
        wsl_path = shutil.which("wsl")

        if not wsl_path:
            self.available = False
            return []

        try:
            status = _run_wsl(["--status"], timeout=20)
            self.status_text = decode_wsl_output(
                status.stdout or status.stderr
            ).strip()

        except (subprocess.TimeoutExpired, OSError):
            self.status_text = ""

        try:
            result = _run_wsl(
                ["--list", "--verbose"],
                timeout=30,
            )

        except (subprocess.TimeoutExpired, OSError) as error:
            raise ScannerError(
                f"Could not read WSL distributions: {error}"
            ) from error

        text = decode_wsl_output(
            result.stdout or result.stderr
        )

        if result.returncode != 0 and not text.strip():
            raise ScannerError(
                "wsl --list --verbose failed."
            )

        return parse_wsl_list(text)
