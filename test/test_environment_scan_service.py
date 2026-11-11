import unittest

from app.models.application import InstalledApplication
from app.models.environment import TerminalSettings
from app.scanner.base import BaseCollector, BaseScanner
from app.services.environment_scan_service import (
    EnvironmentScanService,
)


class FakeScanner(BaseScanner):
    NAME = "Python"
    PACKAGE_ID = "Python.Python.3.13"

    def scan(self):
        return InstalledApplication(
            name=self.NAME,
            version="3.13.16",
            path=r"C:\Python\python.exe",
            installed=True,
            package_id=self.PACKAGE_ID,
        )


class FakeCollector(BaseCollector):
    def __init__(self, name, value):
        super().__init__()
        self.NAME = name
        self.value = value

    def scan(self):
        return self.value


class BrokenCollector(BaseCollector):
    NAME = "Broken collector"

    def scan(self):
        raise RuntimeError("boom")


class FakeEnvironmentCollector(BaseCollector):
    NAME = "Environment variables"

    def __init__(self):
        super().__init__()
        self.secrets = ["OPENAI_API_KEY"]

    def scan(self):
        return {"EDITOR": "code --wait"}


class FakeTerminalCollector(BaseCollector):
    NAME = "Terminal settings"

    def scan(self):
        return TerminalSettings(
            available=True,
            default_profile="PowerShell",
        )


class EnvironmentScanServiceTests(unittest.TestCase):

    def test_broken_collector_does_not_stop_the_scan(self):
        messages = []

        service = EnvironmentScanService(
            application_scanners=[FakeScanner()],
            collectors={
                "vscode_extensions": FakeCollector(
                    "VS Code extensions",
                    ["ms-python.python"],
                ),
                "git_config": BrokenCollector(),
                "python_packages": FakeCollector(
                    "Python packages",
                    ["Django==5.2.4"],
                ),
                "npm_packages": FakeCollector(
                    "npm global packages",
                    ["typescript"],
                ),
                "wsl_distributions": FakeCollector(
                    "WSL distributions",
                    [],
                ),
                "environment_variables": (
                    FakeEnvironmentCollector()
                ),
            },
            terminal_scanner=FakeTerminalCollector(),
        )

        snapshot = service.scan(report=messages.append)

        self.assertEqual(
            [application.name for application in snapshot.applications],
            ["Python"],
        )
        self.assertEqual(
            snapshot.vscode_extensions,
            ["ms-python.python"],
        )
        self.assertEqual(
            snapshot.git_config,
            {},
        )
        self.assertEqual(
            snapshot.errors,
            ["Broken collector: boom"],
        )
        self.assertEqual(
            snapshot.secret_environment_variables,
            ["OPENAI_API_KEY"],
        )
        self.assertEqual(
            snapshot.environment_variables,
            {"EDITOR": "code --wait"},
        )
        self.assertTrue(snapshot.terminal.available)
        self.assertEqual(
            snapshot.capabilities,
            {
                "python": True,
                "git": True,
                "npm": True,
                "wsl": True,
                "vscode": True,
                "terminal": True,
            },
        )
        self.assertIn(
            "Scanning Python packages...",
            messages,
        )
        self.assertIn(
            "Scanning Terminal settings...",
            messages,
        )


if __name__ == "__main__":
    unittest.main()
