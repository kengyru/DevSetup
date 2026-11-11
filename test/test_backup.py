import json
import tempfile
import unittest
from pathlib import Path

from app.backup.exporter import SetupExporter
from app.backup.importer import SetupImporter
from app.models.application import InstalledApplication
from app.models.environment import (
    TerminalSettings,
    WslDistribution,
)
from app.models.setup import Setup


class SetupFileTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "backend.setup"

    def test_round_trip(self):
        setup = Setup(
            name="backend",
            applications=[
                InstalledApplication(
                    name="Python",
                    version="3.13.16",
                    path=r"C:\Python\python.exe",
                    installed=True,
                    package_id="Python.Python.3.13",
                ),
                InstalledApplication(
                    name="Docker",
                    version="Not installed",
                    path=None,
                    installed=False,
                    package_id="Docker.DockerDesktop",
                ),
            ],
        )

        SetupExporter().export(setup, self.path)
        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(imported.name, "backend")
        self.assertEqual(len(imported.applications), 2)

        python = imported.applications[0]
        docker = imported.applications[1]

        self.assertEqual(python.name, "Python")
        self.assertEqual(python.version, "3.13.16")
        self.assertEqual(python.path, r"C:\Python\python.exe")
        self.assertTrue(python.installed)
        self.assertEqual(
            python.package_id,
            "Python.Python.3.13",
        )

        # A tool the user wants but does not have stays in the setup.
        self.assertEqual(docker.name, "Docker")
        self.assertFalse(docker.installed)
        self.assertEqual(
            docker.package_id,
            "Docker.DockerDesktop",
        )

    def test_file_is_plain_json(self):
        setup = Setup(
            name="backend",
            applications=[
                InstalledApplication("Git", "2.56.0", None, True)
            ],
        )

        SetupExporter().export(setup, self.path)

        data = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(data["format_version"], 2)
        self.assertEqual(data["name"], "backend")
        self.assertEqual(data["applications"][0]["name"], "Git")

    def test_legacy_file_without_package_id_gets_it_from_name(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 1,
                    "name": "legacy",
                    "applications": [
                        {
                            "name": "Git",
                            "version": "2.40.0",
                            "path": None,
                            "installed": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(
            imported.applications[0].package_id,
            "Git.Git",
        )

    def test_missing_format_version_is_accepted(self):
        self.path.write_text(
            json.dumps(
                {
                    "name": "old",
                    "applications": [],
                }
            ),
            encoding="utf-8",
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(imported.name, "old")

    def test_invalid_json_raises_value_error(self):
        self.path.write_text("{not json", encoding="utf-8")

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))

    def test_non_object_root_raises_value_error(self):
        self.path.write_text("[1, 2, 3]", encoding="utf-8")

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))

    def test_applications_must_be_a_list(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 1,
                    "name": "broken",
                    "applications": {},
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))

    def test_application_without_name_raises_value_error(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 1,
                    "name": "broken",
                    "applications": [
                        {"version": "1.0", "installed": True}
                    ],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))

    def test_unsupported_format_version_raises_value_error(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 99,
                    "name": "future",
                    "applications": [],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            SetupImporter().import_setup(
                str(Path(self.temp_dir.name) / "nope.setup")
            )

    def test_directory_raises_value_error(self):
        with self.assertRaises(ValueError):
            SetupImporter().import_setup(self.temp_dir.name)


class Stage2SetupFormatTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "dev.setup"

    def full_setup(self):
        return Setup(
            name="full",
            applications=[
                InstalledApplication(
                    name="VS Code",
                    version="1.143.1",
                    path=r"C:\VSCode\bin\code.cmd",
                    installed=True,
                    package_id="Microsoft.VisualStudioCode",
                ),
                InstalledApplication(
                    name="Git",
                    version="git version 2.56.0.windows.2",
                    path=r"C:\Git\git.exe",
                    installed=True,
                    package_id="Git.Git",
                ),
            ],
            vscode_extensions=[
                "ms-python.python",
                "ms-azuretools.vscode-docker",
            ],
            git_config={
                "user.name": "Ann",
                "core.editor": "code --wait",
                "credential.helper": "manager",
            },
            python_packages=[
                "Django==5.2.4",
                "requests==2.32.3",
            ],
            npm_packages=["typescript"],
            wsl_distributions=[
                WslDistribution("Ubuntu-22.04", 2, "Running")
            ],
            environment_variables={
                "EDITOR": "code --wait",
                "OPENAI_API_KEY": "sk-must-not-be-written",
            },
            secret_environment_variables=["GITHUB_TOKEN"],
            terminal=TerminalSettings(
                available=True,
                settings_path=r"C:\settings.json",
                default_profile="PowerShell",
                profiles=["PowerShell"],
                font_face="Cascadia Code",
                color_scheme="Campbell",
            ),
        )

    def test_version_2_round_trip(self):
        SetupExporter().export(self.full_setup(), self.path)

        data = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(data["format_version"], 2)

        vs_code = data["applications"][0]
        self.assertEqual(
            vs_code["extensions"],
            [
                "ms-azuretools.vscode-docker",
                "ms-python.python",
            ],
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(imported.format_version, 2)
        self.assertEqual(
            imported.vscode_extensions,
            [
                "ms-azuretools.vscode-docker",
                "ms-python.python",
            ],
        )
        self.assertEqual(
            imported.git_config,
            {
                "user.name": "Ann",
                "core.editor": "code --wait",
            },
        )
        self.assertEqual(
            imported.python_packages,
            ["Django==5.2.4", "requests==2.32.3"],
        )
        self.assertEqual(imported.npm_packages, ["typescript"])
        self.assertEqual(
            [item.name for item in imported.wsl_distributions],
            ["Ubuntu-22.04"],
        )
        self.assertEqual(
            imported.environment_variables,
            {"EDITOR": "code --wait"},
        )
        self.assertEqual(
            imported.terminal.default_profile,
            "PowerShell",
        )

    def test_secret_values_are_never_written(self):
        SetupExporter().export(self.full_setup(), self.path)

        raw_text = self.path.read_text(encoding="utf-8")
        data = json.loads(raw_text)

        self.assertNotIn("sk-must-not-be-written", raw_text)
        self.assertNotIn(
            "OPENAI_API_KEY",
            data["environment_variables"],
        )
        self.assertIn(
            "OPENAI_API_KEY",
            data["secret_environment_variables"],
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertNotIn(
            "OPENAI_API_KEY",
            imported.environment_variables,
        )
        self.assertIn(
            "OPENAI_API_KEY",
            imported.secret_environment_variables,
        )

    def test_unsafe_entries_are_filtered(self):
        setup = self.full_setup()
        setup.vscode_extensions = [
            "ms-python.python",
            "../bad extension",
        ]
        setup.python_packages = [
            "Django==5.2.4",
            "git+https://evil.test/repo.git",
            "-r requirements.txt",
            "requests",
        ]
        setup.npm_packages = [
            "typescript",
            "bad name",
            "@scope/pkg",
        ]
        setup.git_config = {
            "user.name": "Ann",
            "credential.helper": "manager",
            "alias.lol": "!calc",
            "url.https://token@example=.insteadOf": "x",
        }
        setup.wsl_distributions = [
            WslDistribution("Ubuntu-22.04", 2),
            WslDistribution("-d", 2),
        ]

        SetupExporter().export(setup, self.path)

        data = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(
            data["python_packages"],
            ["Django==5.2.4"],
        )
        self.assertEqual(
            data["npm_packages"],
            ["typescript", "@scope/pkg"],
        )
        self.assertEqual(
            data["git_config"],
            {"user.name": "Ann"},
        )
        self.assertEqual(
            [
                item["name"]
                for item in data["wsl_distributions"]
            ],
            ["Ubuntu-22.04"],
        )
        self.assertEqual(
            data["applications"][0]["extensions"],
            ["ms-python.python"],
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(
            imported.python_packages,
            ["Django==5.2.4"],
        )
        self.assertEqual(
            imported.git_config,
            {"user.name": "Ann"},
        )

    def test_v1_file_still_imports(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 1,
                    "name": "legacy",
                    "applications": [
                        {
                            "name": "Python",
                            "version": "3.13.16",
                            "path": None,
                            "installed": True,
                            "package_id": "Python.Python.3.13",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(imported.format_version, 1)
        self.assertEqual(len(imported.applications), 1)
        self.assertEqual(imported.vscode_extensions, [])
        self.assertEqual(imported.git_config, {})
        self.assertEqual(imported.python_packages, [])
        self.assertEqual(imported.npm_packages, [])
        self.assertEqual(imported.wsl_distributions, [])
        self.assertEqual(imported.environment_variables, {})
        self.assertFalse(imported.terminal.available)

    def test_untrusted_package_id_is_ignored(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "name": "tampered",
                    "applications": [
                        {
                            "name": "Git",
                            "version": "2.56.0",
                            "path": None,
                            "installed": True,
                            "package_id": "Evil.Package",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(
            imported.applications[0].package_id,
            "Git.Git",
        )

    def test_top_level_extensions_are_accepted(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "name": "extensions only",
                    "applications": [],
                    "vscode_extensions": [
                        "ms-python.python",
                        "bad extension",
                    ],
                }
            ),
            encoding="utf-8",
        )

        imported = SetupImporter().import_setup(str(self.path))

        self.assertEqual(
            imported.vscode_extensions,
            ["ms-python.python"],
        )

    def test_corrupted_v2_section_raises(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "name": "broken",
                    "applications": [],
                    "python_packages": "Django==5.2.4",
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))

    def test_corrupted_wsl_section_raises(self):
        self.path.write_text(
            json.dumps(
                {
                    "format_version": 2,
                    "name": "broken",
                    "applications": [],
                    "wsl_distributions": {},
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            SetupImporter().import_setup(str(self.path))


if __name__ == "__main__":
    unittest.main()
