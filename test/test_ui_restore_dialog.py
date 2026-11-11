import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QPushButton,
)

from app.models.application import InstalledApplication
from app.models.environment import (
    EnvironmentSnapshot,
    TerminalSettings,
    WslDistribution,
)
from app.models.setup import Setup
from app.services.environment_compare_service import (
    EnvironmentCompareService,
)
from app.ui.main_window import MainWindow
from app.ui.restore_dialog import RestoreDialog

_APP = QApplication.instance() or QApplication([])


def build_report():
    setup = Setup(
        name="ui",
        applications=[
            InstalledApplication("Python", "3.13.16", None, True),
            InstalledApplication("Git", "2.56.0", None, True),
            InstalledApplication("Docker", "27.0.3", None, True),
        ],
        vscode_extensions=[
            "ms-python.python",
            "ms-python.vscode-pylance",
        ],
        git_config={
            "user.name": "Ann",
            "user.email": "ann@example.test",
        },
        python_packages=["Django==5.2.4"],
        npm_packages=["typescript"],
        wsl_distributions=[WslDistribution("Ubuntu", 2)],
        environment_variables={"EDITOR": "code --wait"},
        terminal=TerminalSettings(available=True),
    )

    snapshot = EnvironmentSnapshot(
        applications=[
            InstalledApplication("Python", "3.13.16", None, True),
            InstalledApplication("Git", "2.40.1", None, True),
            InstalledApplication(
                "Docker", "Not installed", None, False
            ),
        ],
        vscode_extensions=["ms-python.python"],
        git_config={"user.name": "Bob"},
        python_packages=[],
        npm_packages=[],
        wsl_distributions=[],
        environment_variables={},
        secret_environment_variables=["OPENAI_API_KEY"],
        terminal=TerminalSettings(available=True),
        capabilities={
            "python": True,
            "git": True,
            "npm": True,
            "wsl": True,
            "vscode": True,
            "terminal": True,
        },
    )

    return EnvironmentCompareService().compare(setup, snapshot)


class RestoreDialogTests(unittest.TestCase):

    def test_default_selection_is_opt_in_for_risky_items(self):
        dialog = RestoreDialog(build_report())
        self.addCleanup(dialog.deleteLater)

        selection = dialog.selection()

        self.assertEqual(
            [application.name for application in selection.applications],
            ["Docker"],
        )
        self.assertEqual(selection.version_restores, [])
        self.assertEqual(
            selection.extensions,
            ["ms-python.vscode-pylance"],
        )
        self.assertEqual(
            selection.python_packages,
            ["Django==5.2.4"],
        )
        self.assertEqual(selection.npm_packages, ["typescript"])
        self.assertEqual(
            selection.git_config,
            {
                "user.name": "Ann",
                "user.email": "ann@example.test",
            },
        )
        self.assertEqual(selection.environment_variables, {})
        self.assertEqual(selection.wsl_distributions, [])

    def test_unchecking_everything_restores_nothing(self):
        dialog = RestoreDialog(build_report())
        self.addCleanup(dialog.deleteLater)

        for box in dialog.findChildren(QCheckBox):
            box.setChecked(False)

        self.assertTrue(dialog.selection().is_empty)

    def test_selecting_everything_builds_a_full_selection(self):
        dialog = RestoreDialog(build_report())
        self.addCleanup(dialog.deleteLater)

        for box in dialog.findChildren(QCheckBox):
            box.setChecked(True)

        selection = dialog.selection()

        self.assertEqual(len(selection.version_restores), 1)
        self.assertEqual(
            selection.version_restores[0].name,
            "Git",
        )
        self.assertEqual(
            selection.environment_variables,
            {"EDITOR": "code --wait"},
        )
        self.assertEqual(
            [item.name for item in selection.wsl_distributions],
            ["Ubuntu"],
        )

    def test_secret_name_is_shown_as_not_backed_up(self):
        dialog = RestoreDialog(build_report())
        self.addCleanup(dialog.deleteLater)

        texts = [
            label.text() for label in dialog.findChildren(QLabel)
        ]

        self.assertTrue(
            any(
                "OPENAI_API_KEY" in text
                and "Secret — not backed up" in text
                for text in texts
            )
        )


class MainWindowReportTests(unittest.TestCase):

    def test_version_mismatch_has_restore_button_and_categories(self):
        window = MainWindow()
        self.addCleanup(window.deleteLater)

        window.show_report(build_report())

        button_texts = [
            button.text()
            for button in window.findChildren(QPushButton)
        ]

        self.assertEqual(
            button_texts.count("Restore Version"),
            1,
        )

        labels = [
            label.text()
            for label in window.findChildren(QLabel)
        ]

        self.assertIn("⚠ Version mismatch", labels)
        self.assertTrue(
            any(
                text.startswith("Saved: 2.56.0")
                and "Current: 2.40.1" in text
                for text in labels
            )
        )

        for section in (
            "Applications",
            "VS Code Extensions",
            "Packages",
            "Configuration",
            "WSL",
            "Terminal",
        ):
            with self.subTest(section=section):
                self.assertIn(section, labels)


if __name__ == "__main__":
    unittest.main()
