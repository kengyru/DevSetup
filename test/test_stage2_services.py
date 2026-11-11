import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.core.process import ProcessResult
from app.models.application import InstalledApplication
from app.models.comparison import ComparisonStatus
from app.models.environment import (
    EnvironmentSnapshot,
    TerminalSettings,
    WslDistribution,
)
from app.models.restore import (
    OperationResult,
    RestoreSelection,
    VersionRestoreItem,
)
from app.models.setup import Setup
from app.services.config_service import (
    EnvironmentVariableService,
    GitConfigService,
)
from app.services.environment_compare_service import (
    EnvironmentCompareService,
)
from app.services.environment_restore_service import (
    EnvironmentRestoreService,
)
from app.services.extension_service import ExtensionService
from app.services.package_service import PackageService
from app.services.restore_service import RestoreService
from app.services.wsl_service import WSLService


def _winget(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class VersionRestoreTests(unittest.TestCase):

    def setUp(self):
        self.service = RestoreService()
        self.application = InstalledApplication(
            name="Python",
            version="3.13.16",
            installed=True,
            package_id="Evil.Package.Should.Be.Ignored",
        )

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_exact_version_is_installed(self, _which, run):
        def side_effect(command, **_kwargs):
            if "show" in command:
                return _winget(
                    stdout=(
                        "Found Python [Python.Python.3.13]\n"
                        "Version\n"
                        "-------\n"
                        "3.13.15\n"
                        "3.13.16\n"
                    )
                )

            return _winget(stdout="Successfully installed")

        run.side_effect = side_effect

        success, message = self.service.install_version(
            self.application,
            "3.13.16",
        )

        self.assertTrue(success)
        self.assertIn("3.13.16", message)

        commands = [
            call.args[0] for call in run.call_args_list
        ]

        self.assertEqual(commands[0][1], "show")
        self.assertEqual(commands[1][1], "install")
        self.assertIn("--version", commands[1])
        self.assertEqual(
            commands[1][commands[1].index("--version") + 1],
            "3.13.16",
        )
        self.assertIn(
            "Python.Python.3.13",
            commands[1],
        )
        self.assertNotIn(
            "Evil.Package.Should.Be.Ignored",
            commands[1],
        )

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_unavailable_version_is_not_guessed(self, _which, run):
        run.return_value = _winget(
            stdout=(
                "Found Python [Python.Python.3.13]\n"
                "Version\n"
                "-------\n"
                "3.13.15\n"
            )
        )

        success, message = self.service.install_version(
            self.application,
            "3.13.16",
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Required version is not available through winget.",
        )
        self.assertEqual(run.call_count, 1)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_failed_version_listing_uses_the_same_error(
        self,
        _which,
        run,
    ):
        run.return_value = _winget(
            returncode=1,
            stderr="No package found",
        )

        success, message = self.service.install_version(
            self.application,
            "3.13.16",
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Required version is not available through winget.",
        )

    @mock.patch(
        "app.services.restore_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            cmd="winget",
            timeout=120,
        ),
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_version_listing_timeout_uses_the_same_error(
        self,
        _which,
        _run,
    ):
        success, message = self.service.install_version(
            self.application,
            "3.13.16",
        )

        self.assertFalse(success)
        self.assertEqual(
            message,
            "Required version is not available through winget.",
        )

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_already_installed_version_is_success(self, _which, run):
        def side_effect(command, **_kwargs):
            if "show" in command:
                return _winget(stdout="3.13.16\n")

            return _winget(
                returncode=1,
                stdout="Package already installed",
            )

        run.side_effect = side_effect

        success, message = self.service.install_version(
            self.application,
            "3.13.16",
        )

        self.assertTrue(success)
        self.assertIn("already installed", message)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_install_uses_allowlisted_package_id(self, _which, run):
        run.return_value = _winget(stdout="Successfully installed")

        success, _message = self.service.install(
            InstalledApplication(
                name="Docker",
                version="27.0.3",
                installed=True,
                package_id="Evil.Package",
            )
        )

        self.assertTrue(success)
        self.assertIn(
            "Docker.DockerDesktop",
            run.call_args.args[0],
        )
        self.assertNotIn(
            "Evil.Package",
            run.call_args.args[0],
        )


class ExtensionServiceTests(unittest.TestCase):

    @mock.patch(
        "app.services.extension_service.subprocess.run",
    )
    def test_extension_is_installed(self, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout="Extension installed",
            stderr="",
        )

        service = ExtensionService(
            code_path=r"C:\VSCode\bin\code.cmd"
        )

        success, message = service.install("ms-python.python")

        self.assertTrue(success)
        self.assertIn("installed", message)

        command = run.call_args.args[0]
        self.assertIn("--install-extension", command)
        self.assertIn("ms-python.python", command)

    def test_invalid_extension_id_is_rejected(self):
        with mock.patch(
            "app.services.extension_service.subprocess.run"
        ) as run:
            service = ExtensionService(
                code_path=r"C:\VSCode\bin\code.cmd"
            )

            success, message = service.install(
                "ms-python.python; rm -rf /"
            )

        self.assertFalse(success)
        self.assertIn("not a valid", message)
        run.assert_not_called()

    def test_missing_vscode_is_reported(self):
        with mock.patch(
            "app.services.extension_service.VSCodeScanner.find_path",
            return_value=None,
        ):
            success, message = ExtensionService().install(
                "ms-python.python"
            )

        self.assertFalse(success)
        self.assertEqual(message, "VS Code is not installed.")

    @mock.patch(
        "app.services.extension_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            cmd="code",
            timeout=300,
        ),
    )
    def test_timeout_is_reported(self, _run):
        service = ExtensionService(
            code_path=r"C:\VSCode\bin\code.cmd"
        )

        success, message = service.install("ms-python.python")

        self.assertFalse(success)
        self.assertIn("took longer", message)


class PythonPackageServiceTests(unittest.TestCase):

    @mock.patch(
        "app.services.package_service.run_process",
    )
    def test_pinned_packages_use_a_requirements_file(self, run):
        captured = {}

        def side_effect(command, timeout):
            path = Path(command[-1])
            captured["command"] = command
            captured["content"] = path.read_text(encoding="utf-8")
            captured["path"] = path
            return ProcessResult(returncode=0, output="")

        run.side_effect = side_effect

        service = PackageService(
            python_path=r"C:\Python\python.exe"
        )

        results = service.install_python(
            ["Django==5.2.4", "git+https://evil.test/repo.git"]
        )

        self.assertEqual(
            [result.success for result in results],
            [True, False],
        )
        self.assertEqual(
            captured["content"],
            "Django==5.2.4\n",
        )
        self.assertIn("-r", captured["command"])
        self.assertIn(
            "requirements",
            str(captured["path"]).lower(),
        )
        self.assertFalse(captured["path"].exists())

    @mock.patch(
        "app.services.package_service.run_process",
        return_value=ProcessResult(
            returncode=1,
            output="ERROR: no network",
        ),
    )
    def test_pip_failure_is_reported(self, _run):
        service = PackageService(
            python_path=r"C:\Python\python.exe"
        )

        results = service.install_python(["Django==5.2.4"])

        self.assertFalse(results[0].success)
        self.assertIn("no network", results[0].message)

    @mock.patch(
        "app.services.package_service.find_global_python",
        return_value=None,
    )
    def test_missing_python_is_reported(self, _find):
        results = PackageService().install_python(
            ["Django==5.2.4"]
        )

        self.assertFalse(results[0].success)
        self.assertEqual(
            results[0].message,
            "Python is not installed.",
        )

    @mock.patch(
        "app.services.package_service.run_process",
        return_value=ProcessResult(returncode=0, output=""),
    )
    def test_npm_installs_valid_packages_one_by_one(self, run):
        service = PackageService(
            npm_path=r"C:\nodejs\npm.cmd"
        )

        results = service.install_npm(
            ["typescript", "bad name", "@scope/pkg"]
        )

        by_name = {result.name: result for result in results}

        self.assertTrue(by_name["typescript"].success)
        self.assertTrue(by_name["@scope/pkg"].success)
        self.assertFalse(by_name["bad name"].success)
        self.assertEqual(run.call_count, 2)

        command = run.call_args_list[0].args[0]
        self.assertIn("install", command)
        self.assertIn("-g", command)
        self.assertIn("typescript", command)

    @mock.patch(
        "app.services.package_service.find_npm",
        return_value=None,
    )
    def test_missing_npm_is_reported(self, _find):
        results = PackageService().install_npm(["typescript"])

        self.assertFalse(results[0].success)
        self.assertEqual(
            results[0].message,
            "npm is not installed.",
        )


class GitConfigServiceTests(unittest.TestCase):

    @mock.patch(
        "app.services.config_service.run_process",
        return_value=ProcessResult(returncode=0, output=""),
    )
    def test_only_allowlisted_settings_are_applied(self, run):
        service = GitConfigService(
            git_path=r"C:\Git\git.exe"
        )

        results = service.apply(
            {
                "user.name": "Ann",
                "credential.helper": "manager",
                "user.email": "ann@example.test",
            }
        )

        by_name = {result.name: result for result in results}

        self.assertTrue(by_name["user.name"].success)
        self.assertTrue(by_name["user.email"].success)
        self.assertFalse(by_name["credential.helper"].success)
        self.assertEqual(run.call_count, 2)

        command = run.call_args_list[0].args[0]

        self.assertEqual(
            command[1:],
            ["config", "--global", "user.name", "Ann"],
        )

    @mock.patch(
        "app.services.config_service.run_process",
    )
    def test_multiline_value_is_rejected(self, run):
        service = GitConfigService(
            git_path=r"C:\Git\git.exe"
        )

        results = service.apply(
            {"user.name": "Ann\nmalicious"}
        )

        self.assertFalse(results[0].success)
        run.assert_not_called()

    @mock.patch(
        "app.services.config_service.shutil.which",
        return_value=None,
    )
    def test_missing_git_is_reported(self, _which):
        results = GitConfigService().apply(
            {"user.name": "Ann"}
        )

        self.assertFalse(results[0].success)
        self.assertEqual(
            results[0].message,
            "Git is not installed.",
        )


class EnvironmentVariableServiceTests(unittest.TestCase):

    @mock.patch(
        "app.services.config_service._broadcast_environment_change",
    )
    @mock.patch(
        "app.services.config_service.winreg",
    )
    def test_only_safe_variables_are_written(
        self,
        winreg_mock,
        broadcast,
    ):
        key = mock.MagicMock()
        winreg_mock.CreateKeyEx.return_value = key

        service = EnvironmentVariableService()

        results = service.apply(
            {
                "EDITOR": "code --wait",
                "OPENAI_API_KEY": "sk-test",
                "Path": r"C:\Windows",
                "NODE_OPTIONS": "--max-old-space-size=4096",
            }
        )

        by_name = {result.name: result for result in results}

        self.assertTrue(by_name["EDITOR"].success)
        self.assertTrue(by_name["NODE_OPTIONS"].success)
        self.assertFalse(by_name["OPENAI_API_KEY"].success)
        self.assertFalse(by_name["Path"].success)

        self.assertEqual(winreg_mock.SetValueEx.call_count, 2)
        broadcast.assert_called_once()

    @mock.patch(
        "app.services.config_service.winreg",
        None,
    )
    def test_non_windows_is_reported(self):
        results = EnvironmentVariableService().apply(
            {"EDITOR": "vim"}
        )

        self.assertFalse(results[0].success)
        self.assertIn("only be restored on Windows", results[0].message)


class WSLServiceTests(unittest.TestCase):

    @mock.patch(
        "app.services.wsl_service.run_process",
        return_value=ProcessResult(
            returncode=0,
            output="Installing",
        ),
    )
    @mock.patch(
        "app.services.wsl_service.shutil.which",
        return_value=r"C:\Windows\System32\wsl.exe",
    )
    def test_distribution_install_is_started(self, _which, run):
        result = WSLService().install(
            WslDistribution("Ubuntu-22.04", 2, "Stopped")
        )

        self.assertTrue(result.success)
        self.assertIn("reboot", result.message)

        command = run.call_args.args[0]

        self.assertEqual(
            command[1:],
            [
                "--install",
                "-d",
                "Ubuntu-22.04",
                "--no-launch",
            ],
        )

    def test_invalid_name_is_rejected(self):
        with mock.patch(
            "app.services.wsl_service.run_process"
        ) as run:
            result = WSLService().install(
                SimpleNamespace(name="-d")
            )

        self.assertFalse(result.success)
        run.assert_not_called()

    @mock.patch(
        "app.services.wsl_service.shutil.which",
        return_value=None,
    )
    def test_missing_wsl_is_reported(self, _which):
        result = WSLService().install(
            WslDistribution("Ubuntu", 2)
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, "WSL is not installed.")


class FakeReporter:

    def __init__(self):
        self.texts = []
        self.progress = []

    def set_text(self, text):
        self.texts.append(text)

    def set_progress(self, current, total):
        self.progress.append((current, total))


class FakeRestoreService:

    def __init__(self, log):
        self.log = log

    def install(self, application):
        self.log.append(f"app:{application.name}")
        return True, "ok"

    def install_version(self, application, version):
        self.log.append(f"version:{application.name}:{version}")
        return True, "ok"


class FakeExtensionService:

    def __init__(self, log):
        self.log = log

    def install(self, extension_id):
        self.log.append(f"ext:{extension_id}")
        return True, "ok"


class FakePackageService:

    def __init__(self, log):
        self.log = log

    def install_python(self, entries):
        self.log.append("python:" + ",".join(entries))
        return [
            OperationResult(entry, True, "ok")
            for entry in entries
        ]

    def install_npm(self, names):
        self.log.append("npm:" + ",".join(names))
        return [
            OperationResult(name, True, "ok")
            for name in names
        ]


class FakeGitConfigService:

    def __init__(self, log):
        self.log = log

    def apply(self, settings):
        self.log.append("git:" + ",".join(settings))
        return [
            OperationResult(key, True, "ok")
            for key in settings
        ]


class FakeEnvironmentService:

    def __init__(self, log):
        self.log = log

    def apply(self, variables):
        self.log.append("env:" + ",".join(variables))
        return [
            OperationResult(name, True, "ok")
            for name in variables
        ]


class FakeWSLService:

    def __init__(self, log):
        self.log = log

    def install(self, distribution):
        self.log.append(f"wsl:{distribution.name}")
        return OperationResult(
            distribution.name,
            True,
            "ok",
        )


class EnvironmentRestoreServiceTests(unittest.TestCase):

    def build_service(self, log):
        return EnvironmentRestoreService(
            restore_service=FakeRestoreService(log),
            extension_service=FakeExtensionService(log),
            package_service=FakePackageService(log),
            git_config_service=FakeGitConfigService(log),
            environment_service=FakeEnvironmentService(log),
            wsl_service=FakeWSLService(log),
        )

    def test_selected_items_are_restored_in_order(self):
        log = []
        reporter = FakeReporter()

        selection = RestoreSelection(
            applications=[
                InstalledApplication(
                    "Python", "3.13.16", None, True
                )
            ],
            version_restores=[
                VersionRestoreItem(
                    InstalledApplication(
                        "Git", "2.40.1", None, True
                    ),
                    "2.40.1",
                )
            ],
            extensions=["ms-python.python"],
            python_packages=["Django==5.2.4"],
            npm_packages=["typescript"],
            git_config={"user.name": "Ann"},
            environment_variables={"EDITOR": "code --wait"},
            wsl_distributions=[WslDistribution("Ubuntu", 2)],
        )

        result = self.build_service(log).run(
            selection,
            reporter,
        )

        self.assertFalse(result.has_failures)
        self.assertEqual(result.total, 8)
        self.assertEqual(
            log,
            [
                "app:Python",
                "version:Git:2.40.1",
                "ext:ms-python.python",
                "python:Django==5.2.4",
                "npm:typescript",
                "git:user.name",
                "env:EDITOR",
                "wsl:Ubuntu",
            ],
        )
        self.assertEqual(reporter.progress[-1], (8, 8))
        self.assertIn("Installing Python...", reporter.texts)
        self.assertIn(
            "Restoring Python packages...",
            reporter.texts,
        )

    def test_empty_selection_restores_nothing(self):
        log = []
        reporter = FakeReporter()

        result = self.build_service(log).run(
            RestoreSelection(),
            reporter,
        )

        self.assertEqual(result.total, 0)
        self.assertEqual(log, [])
        self.assertEqual(reporter.progress[-1], (0, 0))


class EnvironmentCompareServiceTests(unittest.TestCase):

    def test_all_sections_are_compared(self):
        setup = Setup(
            name="dev",
            applications=[
                InstalledApplication(
                    "Python", "3.13.16", None, True
                )
            ],
            vscode_extensions=[
                "ms-python.python",
                "ms-python.vscode-pylance",
            ],
            git_config={
                "user.name": "Ann",
                "user.email": "ann@example.test",
                "credential.helper": "manager",
            },
            python_packages=["Django==5.0.0"],
            npm_packages=["typescript"],
            wsl_distributions=[
                WslDistribution("Ubuntu", 2)
            ],
            environment_variables={
                "EDITOR": "code --wait",
                "OPENAI_API_KEY": "sk-test",
            },
            terminal=TerminalSettings(
                available=True,
                default_profile="PowerShell",
            ),
        )

        snapshot = EnvironmentSnapshot(
            applications=[
                InstalledApplication(
                    "Python", "3.13.12", None, True
                )
            ],
            vscode_extensions=["ms-python.python"],
            git_config={
                "user.name": "Bob",
                "user.email": "old@example.test",
            },
            python_packages=["Django==5.0.0"],
            npm_packages=[],
            wsl_distributions=[],
            environment_variables={"EDITOR": "vim"},
            secret_environment_variables=[
                "OPENAI_API_KEY"
            ],
            terminal=TerminalSettings(
                available=True,
                default_profile="PowerShell",
            ),
        )

        report = EnvironmentCompareService().compare(
            setup,
            snapshot,
        )

        self.assertIs(
            report.applications[0].status,
            ComparisonStatus.VERSION_MISMATCH,
        )
        self.assertEqual(
            report.extensions.missing,
            ("ms-python.vscode-pylance",),
        )
        self.assertIn("user.name", report.git_config.mismatched)
        self.assertIn("user.email", report.git_config.mismatched)
        self.assertNotIn(
            "credential.helper",
            report.git_config.saved,
        )
        self.assertTrue(report.python_packages.in_sync)
        self.assertEqual(
            [package.name for package in report.npm_packages.missing],
            ["typescript"],
        )
        self.assertEqual(
            [item.name for item in report.wsl.missing],
            ["Ubuntu"],
        )
        self.assertIn("EDITOR", report.environment.mismatched_names)
        self.assertIn(
            "OPENAI_API_KEY",
            report.environment.secrets,
        )
        self.assertGreater(report.restorable_item_count, 0)


if __name__ == "__main__":
    unittest.main()
