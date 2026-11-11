"""Installs VS Code extensions with `code --install-extension`."""

import os
import subprocess

from app.core.requirements import is_valid_extension_id
from app.scanner.vscode import VSCodeScanner

_CREATE_NO_WINDOW = 0x08000000

_INSTALL_TIMEOUT = 300


class ExtensionService:
    """Installs one extension at a time so failures stay isolated."""

    NAME = "VS Code extensions"

    def __init__(self, code_path: str | None = None):
        self.code_path = code_path

    def find_code(self) -> str | None:
        if self.code_path:
            return self.code_path

        return VSCodeScanner().find_path()

    def is_available(self) -> bool:
        return self.find_code() is not None

    def install(self, extension_id: str) -> tuple[bool, str]:
        if not is_valid_extension_id(extension_id):
            return False, (
                f"'{extension_id}' is not a valid VS Code "
                "extension id."
            )

        code_path = self.find_code()

        if not code_path:
            return False, "VS Code is not installed."

        if os.name == "nt" and code_path.lower().endswith(
            (".cmd", ".bat")
        ):
            command = [
                "cmd",
                "/c",
                code_path,
                "--install-extension",
                extension_id,
            ]

        else:
            command = [
                code_path,
                "--install-extension",
                extension_id,
            ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_INSTALL_TIMEOUT,
                creationflags=(
                    _CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )

        except subprocess.TimeoutExpired:
            return False, (
                f"Installing {extension_id} took longer than "
                f"{_INSTALL_TIMEOUT} seconds and was stopped."
            )

        except OSError as error:
            return False, (
                f"Could not start VS Code: {error}"
            )

        output = (
            (result.stdout or "").strip()
            or (result.stderr or "").strip()
        )

        if result.returncode == 0:
            return True, f"{extension_id} installed."

        if not output:
            return False, (
                f"VS Code exited with code {result.returncode} "
                f"while installing {extension_id}."
            )

        return False, (
            f"VS Code exited with code {result.returncode}: "
            f"{output[:500]}"
        )
