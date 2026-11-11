import os
import re
import shutil
import subprocess

from app.core.packages import PACKAGE_IDS, get_package_id

_INSTALL_TIMEOUT = 1800

_CREATE_NO_WINDOW = 0x08000000

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# winget HRESULTs that mean "nothing to do" rather than "failed".
_ALREADY_INSTALLED_CODES = {
    -1978335135,  # 0x8A150061 PACKAGE_ALREADY_INSTALLED
    -1978335189,  # 0x8A15002B UPDATE_NOT_APPLICABLE
}

_ALREADY_INSTALLED_TEXT = (
    "already installed",
    "no applicable upgrade",
    "no newer package versions",
)

_NOT_FOUND_TEXT = (
    "no package found",
    "no packages found",
    "no manifest found",
)

_VERSION_NOT_AVAILABLE = (
    "Required version is not available through winget."
)

_WINGET_VERSION_RE = re.compile(
    r"^\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?$"
)


class RestoreService:
    """Installs missing applications through winget."""

    PACKAGE_IDS = PACKAGE_IDS

    def get_package_id(self, application_name: str) -> str | None:
        return get_package_id(application_name)

    def is_available(self) -> bool:
        """Return True when winget is available on this PC."""

        return shutil.which("winget") is not None

    def install(self, application) -> tuple[bool, str]:
        """Install one application.

        ``application`` may be an InstalledApplication or a plain name.
        Returns ``(success, message)`` and never raises.
        """

        if isinstance(application, str):
            name = application
            package_id = get_package_id(application)

        else:
            name = getattr(application, "name", str(application))
            # The setup file's package_id is informational only. Restore
            # always uses the local allowlist.
            package_id = get_package_id(name)

        if not package_id:
            return False, (
                f"No winget package id is known for '{name}'. "
                "Install it manually."
            )

        winget_path = shutil.which("winget")

        if not winget_path:
            return False, (
                "winget was not found on this computer. "
                "Install 'App Installer' from the Microsoft Store "
                "and try again."
            )

        command = [
            winget_path,
            "install",
            "--id",
            package_id,
            "-e",
            "--source",
            "winget",
            "--accept-source-agreements",
            "--accept-package-agreements",
            "--disable-interactivity",
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
                f"Installing {name} took longer than "
                f"{_INSTALL_TIMEOUT // 60} minutes and was stopped."
            )

        except OSError as error:
            return False, f"Could not start winget: {error}"

        output = self._clean_output(
            f"{result.stdout or ''}\n{result.stderr or ''}"
        )

        if result.returncode == 0:
            return True, f"{name} installed successfully."

        if result.returncode in _ALREADY_INSTALLED_CODES:
            return True, f"{name} is already installed."

        lowered = output.lower()

        if any(text in lowered for text in _ALREADY_INSTALLED_TEXT):
            return True, f"{name} is already installed."

        if any(text in lowered for text in _NOT_FOUND_TEXT):
            return False, (
                f"winget could not find package '{package_id}'. "
                "Check the package id or install it manually."
            )

        if not output:
            return False, (
                f"winget exited with code {result.returncode} "
                f"while installing {name}."
            )

        return False, (
            f"winget exited with code {result.returncode}: {output}"
        )

    def install_version(self, application, version: str) -> tuple[bool, str]:
        """Install one exact version of an application through winget.

        The version is never guessed or downgraded silently: if winget does
        not list the exact saved version, the restore stops with a clear
        error and nothing is installed.
        """

        if isinstance(application, str):
            name = application
            package_id = get_package_id(application)

        else:
            name = getattr(application, "name", str(application))
            # The package id stored in a setup file is informational only.
            # Restore always derives it from the local allowlist.
            package_id = get_package_id(name)

        if not package_id:
            return False, (
                f"No winget package id is known for '{name}'. "
                "Install it manually."
            )

        target_version = (version or "").strip()

        if not target_version:
            return False, (
                f"The setup does not contain a version for '{name}'."
            )

        winget_path = shutil.which("winget")

        if not winget_path:
            return False, (
                "winget was not found on this computer. "
                "Install 'App Installer' from the Microsoft Store "
                "and try again."
            )

        versions = self._get_available_versions(
            winget_path,
            package_id,
        )

        if not any(
            candidate.lower() == target_version.lower()
            for candidate in versions
        ):
            return False, _VERSION_NOT_AVAILABLE

        command = [
            winget_path,
            "install",
            "--id",
            package_id,
            "-e",
            "--version",
            target_version,
            "--source",
            "winget",
            "--accept-source-agreements",
            "--accept-package-agreements",
            "--disable-interactivity",
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
                f"Restoring {name} {target_version} took longer than "
                f"{_INSTALL_TIMEOUT // 60} minutes and was stopped."
            )

        except OSError as error:
            return False, f"Could not start winget: {error}"

        output = self._clean_output(
            f"{result.stdout or ''}\n{result.stderr or ''}"
        )

        if result.returncode == 0:
            return True, (
                f"{name} {target_version} installed successfully."
            )

        if result.returncode in _ALREADY_INSTALLED_CODES:
            return True, (
                f"{name} {target_version} is already installed."
            )

        lowered = output.lower()

        if any(text in lowered for text in _ALREADY_INSTALLED_TEXT):
            return True, (
                f"{name} {target_version} is already installed."
            )

        if any(text in lowered for text in _NOT_FOUND_TEXT):
            return False, _VERSION_NOT_AVAILABLE

        if not output:
            return False, (
                f"winget exited with code {result.returncode} "
                f"while restoring {name} {target_version}."
            )

        return False, (
            f"winget exited with code {result.returncode}: {output}"
        )

    def _get_available_versions(
        self,
        winget_path: str,
        package_id: str,
    ) -> list[str]:
        """Return the versions winget lists for one package."""

        command = [
            winget_path,
            "show",
            "--id",
            package_id,
            "-e",
            "--versions",
            "--source",
            "winget",
            "--accept-source-agreements",
            "--disable-interactivity",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                creationflags=(
                    _CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )

        except (subprocess.TimeoutExpired, OSError):
            return []

        if result.returncode != 0:
            return []

        versions = []

        for line in (result.stdout or "").splitlines():
            candidate = line.strip()

            if _WINGET_VERSION_RE.fullmatch(candidate):
                versions.append(candidate)

        return versions

    @staticmethod
    def _clean_output(text: str) -> str:
        """Strip ANSI codes and control characters from winget output."""

        text = _ANSI_RE.sub("", text or "")

        cleaned_lines = []

        for line in text.splitlines():
            line = "".join(
                character
                for character in line
                if character.isprintable()
            ).strip()

            if line:
                cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines)

        if len(cleaned) > 2000:
            cleaned = "..." + cleaned[-2000:]

        return cleaned
