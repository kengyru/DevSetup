"""Restores safe Git configuration and user environment variables."""

import os
import shutil

from app.core.process import ProcessTimeoutError, run_process
from app.core.secrets import is_safe_environment_name
from app.models.restore import OperationResult
from app.scanner.git_config import is_safe_git_key

try:
    import winreg
except ImportError:  # pragma: no cover - Windows only project
    winreg = None

_GIT_TIMEOUT = 30

_MAX_ENVIRONMENT_VALUE_LENGTH = 4000


class GitConfigService:
    """Applies only the allowlisted, non-secret Git settings."""

    def __init__(self, git_path: str | None = None):
        self._git_path = git_path

    def find_git(self) -> str | None:
        if self._git_path:
            return self._git_path

        return shutil.which("git")

    def is_available(self) -> bool:
        return self.find_git() is not None

    def apply(
        self,
        settings: dict[str, str],
    ) -> list[OperationResult]:
        results: list[OperationResult] = []

        for key, value in settings.items():
            if not is_safe_git_key(key):
                results.append(
                    OperationResult(
                        name=str(key),
                        success=False,
                        message=(
                            "This Git setting is not on the safe "
                            "allowlist and was skipped."
                        ),
                    )
                )
                continue

            if not isinstance(value, str) or any(
                character in value
                for character in ("\x00", "\r", "\n")
            ):
                results.append(
                    OperationResult(
                        name=key,
                        success=False,
                        message="Invalid Git setting value.",
                    )
                )
                continue

            git_path = self.find_git()

            if not git_path:
                results.append(
                    OperationResult(
                        name=key,
                        success=False,
                        message="Git is not installed.",
                    )
                )
                continue

            try:
                result = run_process(
                    [
                        git_path,
                        "config",
                        "--global",
                        key,
                        value,
                    ],
                    timeout=_GIT_TIMEOUT,
                )

            except ProcessTimeoutError:
                results.append(
                    OperationResult(
                        name=key,
                        success=False,
                        message="git config did not finish in time.",
                    )
                )
                continue

            except OSError as error:
                results.append(
                    OperationResult(
                        name=key,
                        success=False,
                        message=f"Could not run git: {error}",
                    )
                )
                continue

            if result.success:
                results.append(
                    OperationResult(
                        name=key,
                        success=True,
                        message="Set.",
                    )
                )
                continue

            results.append(
                OperationResult(
                    name=key,
                    success=False,
                    message=(
                        result.output[:500]
                        or f"git exited with code "
                        f"{result.returncode}."
                    ),
                )
            )

        return results


class EnvironmentVariableService:
    """Writes safe user variables to HKCU\\Environment.

    Values are written with the winreg module, never with a shell
    command, so a setup file cannot execute anything.
    """

    def is_available(self) -> bool:
        return winreg is not None

    def apply(
        self,
        variables: dict[str, str],
    ) -> list[OperationResult]:
        results: list[OperationResult] = []

        valid: list[tuple[str, str]] = []

        for name, value in variables.items():
            if not is_safe_environment_name(name):
                results.append(
                    OperationResult(
                        name=str(name),
                        success=False,
                        message=(
                            "This variable is secret, system managed "
                            "or invalid and was skipped."
                        ),
                    )
                )
                continue

            if not isinstance(value, str):
                results.append(
                    OperationResult(
                        name=name,
                        success=False,
                        message="Invalid environment value.",
                    )
                )
                continue

            if (
                len(value) > _MAX_ENVIRONMENT_VALUE_LENGTH
                or "\x00" in value
            ):
                results.append(
                    OperationResult(
                        name=name,
                        success=False,
                        message="Invalid environment value.",
                    )
                )
                continue

            valid.append((name, value))

        if not valid:
            return results

        if winreg is None:
            return results + [
                OperationResult(
                    name=name,
                    success=False,
                    message=(
                        "Environment variables can only be restored "
                        "on Windows."
                    ),
                )
                for name, _value in valid
            ]

        try:
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                "Environment",
                0,
                winreg.KEY_SET_VALUE,
            )

        except OSError as error:
            return results + [
                OperationResult(
                    name=name,
                    success=False,
                    message=(
                        "Could not open the user environment "
                        f"registry key: {error}"
                    ),
                )
                for name, _value in valid
            ]

        written = False

        with key:
            for name, value in valid:
                value_type = (
                    winreg.REG_EXPAND_SZ
                    if "%" in value
                    else winreg.REG_SZ
                )

                try:
                    winreg.SetValueEx(
                        key,
                        name,
                        0,
                        value_type,
                        value,
                    )

                except OSError as error:
                    results.append(
                        OperationResult(
                            name=name,
                            success=False,
                            message=(
                                "Could not write the variable: "
                                f"{error}"
                            ),
                        )
                    )
                    continue

                written = True
                results.append(
                    OperationResult(
                        name=name,
                        success=True,
                        message="Set.",
                    )
                )

        if written:
            _broadcast_environment_change()

        return results


def _broadcast_environment_change() -> None:
    """Tell running applications that the environment changed."""

    if os.name != "nt":
        return

    try:
        import ctypes

        result = ctypes.c_size_t()
        environment = ctypes.c_wchar_p("Environment")

        send_message = ctypes.windll.user32.SendMessageTimeoutW
        send_message.argtypes = [
            ctypes.c_void_p,  # HWND
            ctypes.c_uint,  # UINT
            ctypes.c_size_t,  # WPARAM
            ctypes.c_size_t,  # LPARAM
            ctypes.c_uint,  # UINT flags
            ctypes.c_uint,  # UINT timeout
            ctypes.POINTER(ctypes.c_size_t),  # result
        ]
        send_message.restype = ctypes.c_ssize_t

        send_message(
            0xFFFF,  # HWND_BROADCAST
            0x001A,  # WM_SETTINGCHANGE
            0,
            ctypes.cast(
                environment,
                ctypes.c_void_p,
            ).value,
            0x0002,  # SMTO_ABORTIFHUNG
            5000,
            ctypes.byref(result),
        )

    except Exception:
        # Broadcasting is a convenience; the registry value is already
        # written even if no window answered.
        pass
