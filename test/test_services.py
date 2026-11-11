import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner
from app.services.restore_service import RestoreService
from app.services.scan_service import ScanService


class BrokenScanner(BaseScanner):
    NAME = "Broken"
    PACKAGE_ID = "Broken.Tool"

    def scan(self):
        raise RuntimeError("boom")


class WorkingScanner(BaseScanner):
    NAME = "Working"
    PACKAGE_ID = "Working.Tool"

    def scan(self):
        return InstalledApplication(
            name=self.NAME,
            version="1.0",
            path=r"C:\tool.exe",
            installed=True,
            package_id=self.PACKAGE_ID,
        )


class ScanServiceTests(unittest.TestCase):

    def test_scanner_error_does_not_stop_the_scan(self):
        service = ScanService(
            scanners=[BrokenScanner(), WorkingScanner()]
        )

        result = service.scan()

        self.assertEqual(len(result), 2)
        self.assertEqual(service.errors, ["Broken: boom"])

        broken = result[0]
        self.assertEqual(broken.name, "Broken")
        self.assertFalse(broken.installed)
        self.assertEqual(broken.package_id, "Broken.Tool")

        self.assertTrue(result[1].installed)


class RestoreServiceTests(unittest.TestCase):

    def setUp(self):
        self.service = RestoreService()
        self.application = InstalledApplication(
            name="Docker",
            version="27.0.3",
            installed=True,
            package_id="Docker.DockerDesktop",
        )

    def test_unknown_application_cannot_be_installed(self):
        success, message = self.service.install(
            InstalledApplication(
                name="Unknown",
                version="1.0",
                installed=True,
            )
        )

        self.assertFalse(success)
        self.assertIn("No winget package id", message)

    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=None,
    )
    def test_missing_winget_is_reported(self, _which):
        success, message = self.service.install(self.application)

        self.assertFalse(success)
        self.assertIn("winget was not found", message)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_successful_install(self, _which, run):
        run.return_value = SimpleNamespace(
            returncode=0,
            stdout="Successfully installed",
            stderr="",
        )

        success, message = self.service.install(self.application)

        self.assertTrue(success)
        self.assertIn("installed successfully", message)

        command = run.call_args.args[0]
        self.assertEqual(command[0], r"C:\winget.exe")
        self.assertEqual(command[1], "install")
        self.assertIn("--id", command)
        self.assertIn("Docker.DockerDesktop", command)
        self.assertIn("--accept-package-agreements", command)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_already_installed_exit_code(self, _which, run):
        run.return_value = SimpleNamespace(
            returncode=-1978335135,
            stdout="",
            stderr="Package already installed",
        )

        success, message = self.service.install(self.application)

        self.assertTrue(success)
        self.assertIn("already installed", message)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_already_installed_text(self, _which, run):
        run.return_value = SimpleNamespace(
            returncode=1,
            stdout="Found Docker Desktop [Docker.DockerDesktop] "
            "already installed.",
            stderr="",
        )

        success, _ = self.service.install(self.application)

        self.assertTrue(success)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_package_not_found(self, _which, run):
        run.return_value = SimpleNamespace(
            returncode=1,
            stdout="No package found matching input criteria.",
            stderr="",
        )

        success, message = self.service.install(self.application)

        self.assertFalse(success)
        self.assertIn("could not find package", message)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_install_error_is_shown(self, _which, run):
        run.return_value = SimpleNamespace(
            returncode=5,
            stdout="",
            stderr="An unexpected error occurred",
        )

        success, message = self.service.install(self.application)

        self.assertFalse(success)
        self.assertIn("unexpected error", message)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            cmd="winget", timeout=1800
        ),
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_timeout_is_reported(self, _which, _run):
        success, message = self.service.install(self.application)

        self.assertFalse(success)
        self.assertIn("took longer", message)

    @mock.patch(
        "app.services.restore_service.subprocess.run",
        side_effect=OSError("access denied"),
    )
    @mock.patch(
        "app.services.restore_service.shutil.which",
        return_value=r"C:\winget.exe",
    )
    def test_os_error_is_reported(self, _which, _run):
        success, message = self.service.install(self.application)

        self.assertFalse(success)
        self.assertIn("Could not start winget", message)


if __name__ == "__main__":
    unittest.main()
