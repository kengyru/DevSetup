"""Suggests WSL distribution installation through `wsl --install`."""

import shutil

from app.core.process import (
    ProcessTimeoutError,
    run_process,
)
from app.core.requirements import is_valid_wsl_name
from app.models.restore import OperationResult

_INSTALL_TIMEOUT = 1800


class WSLService:
    """Installs a WSL distribution; the Linux filesystem is never copied."""

    def find_wsl(self) -> str | None:
        return shutil.which("wsl")

    def is_available(self) -> bool:
        return self.find_wsl() is not None

    def install(self, distribution) -> OperationResult:
        name = getattr(distribution, "name", str(distribution))

        if not is_valid_wsl_name(name):
            return OperationResult(
                name=name,
                success=False,
                message="Invalid WSL distribution name.",
            )

        wsl_path = self.find_wsl()

        if not wsl_path:
            return OperationResult(
                name=name,
                success=False,
                message="WSL is not installed.",
            )

        try:
            result = run_process(
                [
                    wsl_path,
                    "--install",
                    "-d",
                    name,
                    "--no-launch",
                ],
                timeout=_INSTALL_TIMEOUT,
            )

        except ProcessTimeoutError:
            return OperationResult(
                name=name,
                success=False,
                message=(
                    "wsl --install did not finish in time. The "
                    "installation may still be running."
                ),
            )

        except OSError as error:
            return OperationResult(
                name=name,
                success=False,
                message=f"Could not run wsl: {error}",
            )

        if result.success:
            return OperationResult(
                name=name,
                success=True,
                message=(
                    "Installation started. Windows may ask for "
                    "administrator approval and a reboot."
                ),
            )

        return OperationResult(
            name=name,
            success=False,
            message=(
                result.output[:1500]
                or f"wsl exited with code {result.returncode}."
            ),
        )
