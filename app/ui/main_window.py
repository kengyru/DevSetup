import os

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.backup.exporter import SetupExporter
from app.backup.importer import SetupImporter
from app.models.comparison import (
    ComparisonReport,
    ComparisonStatus,
)
from app.models.environment import (
    EnvironmentSnapshot,
    TerminalSettings,
)
from app.models.restore import (
    RestoreResult,
    RestoreSelection,
)
from app.models.setup import Setup
from app.scanner.docker import DockerScanner
from app.scanner.git import GitScanner
from app.scanner.postgresql import PostgreSQLScanner
from app.scanner.python import PythonScanner
from app.scanner.vscode import VSCodeScanner
from app.services.environment_compare_service import (
    EnvironmentCompareService,
)
from app.services.environment_restore_service import (
    EnvironmentRestoreService,
)
from app.services.environment_scan_service import (
    EnvironmentScanService,
)
from app.services.restore_service import RestoreService
from app.ui.application_card import ApplicationCard
from app.ui.restore_dialog import RestoreDialog
from app.ui.summary_card import SummaryCard
from app.ui.worker import Task

_MAX_PREVIEW_LINES = 12


def _preview(value: str, limit: int = 100) -> str:
    text = value.replace("\r", " ").replace("\n", " ")

    if len(text) > limit:
        return text[: limit - 3] + "..."

    return text


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("DevSetup")
        self.resize(980, 760)

        # Everything the last scan found.
        self.snapshot: EnvironmentSnapshot | None = None

        # Current imported setup.
        self.current_setup: Setup | None = None

        # Full comparison of the saved setup with the current PC.
        self.report: ComparisonReport | None = None

        # Applications from the comparison (kept for compatibility).
        self.comparison = []

        # Applications from the last scan (kept for compatibility).
        self.scan_results = []

        # Background task (scan / restore / version restore).
        self._task = None
        self._task_kind = None
        self._task_result = None
        self._task_error = None

        # Scan mode: "scan" or "import".
        self._scan_mode = "scan"

        # Result of the last restore, shown after the follow-up scan.
        self._restore_outcome = None

        self.setup_ui()
        self.update_buttons()

    # ==================================================
    # UI
    # ==================================================

    def setup_ui(self):

        central_widget = QWidget()
        central_widget.setObjectName("Root")
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(12)

        title = QLabel("DevSetup")
        title.setObjectName("Title")

        description = QLabel(
            "Backup and restore your development environment."
        )
        description.setObjectName("Description")

        self.main_layout.addWidget(title)
        self.main_layout.addWidget(description)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.scan_button = QPushButton("Scan PC")
        self.scan_button.setObjectName("Primary")
        self.scan_button.clicked.connect(self.scan_pc)

        self.save_button = QPushButton("Save Setup")
        self.save_button.clicked.connect(self.save_setup)

        self.import_button = QPushButton("Import Setup")
        self.import_button.clicked.connect(self.import_setup)

        self.restore_button = QPushButton("Restore Setup")
        self.restore_button.clicked.connect(self.restore_setup)

        buttons_layout.addWidget(self.scan_button)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.import_button)
        buttons_layout.addWidget(self.restore_button)
        buttons_layout.addStretch(1)

        self.main_layout.addLayout(buttons_layout)

        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("Status")
        self.status_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)

        self.main_layout.addWidget(self.status_label)
        self.main_layout.addWidget(self.progress_bar)

        self.result_title = QLabel(
            "Your Development Environment"
        )
        self.result_title.setObjectName("Section")

        self.main_layout.addWidget(self.result_title)

        self.cards_container = QWidget()
        self.cards_container.setObjectName("Cards")

        self.results_layout = QVBoxLayout(self.cards_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(10)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidget(self.cards_container)

        self.main_layout.addWidget(self.scroll_area, 1)

        self.set_placeholder(
            "Click Scan PC to see your development environment."
        )

    # ==================================================
    # SCANNERS
    # ==================================================

    def create_scanners(self):

        return [
            PythonScanner(),
            GitScanner(),
            VSCodeScanner(),
            DockerScanner(),
            PostgreSQLScanner(),
        ]

    # ==================================================
    # BACKGROUND TASKS
    # ==================================================

    def _start_task(self, kind: str, job):

        if self._task is not None:
            return

        self._task_kind = kind
        self._task_result = None
        self._task_error = None

        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

        task = Task(job, self)
        task.message.connect(self._set_status)
        task.progress.connect(self._set_progress)
        task.done.connect(self._on_task_done)
        task.finished.connect(
            lambda: self._on_task_finished(task)
        )

        self._task = task
        task.start()

        self.update_buttons()

    def _on_task_done(self, result, error):
        # Store the outcome. It is handled in _on_task_finished, right
        # after the thread has fully stopped, so no modal dialog can run
        # while the worker is still alive.
        self._task_result = result
        self._task_error = error

    def _on_task_finished(self, task):

        kind = self._task_kind
        result = self._task_result
        error = self._task_error

        if self._task is task:
            self._task = None

        self._task_kind = None
        self._task_result = None
        self._task_error = None

        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)

        self.update_buttons()
        task.deleteLater()

        if error is not None:
            self._restore_outcome = None
            self._set_status(f"Error: {error}")
            QMessageBox.critical(self, "DevSetup", str(error))
            return

        if result is None:
            self._set_status("Error: the operation returned no result.")
            QMessageBox.critical(
                self,
                "DevSetup",
                "The operation finished without a result. "
                "Please try again.",
            )
            return

        if kind == "scan":
            self._handle_scan_result(result)

        elif kind == "restore":
            self._handle_restore_result(result)

        elif kind == "version":
            self._handle_version_result(result)

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _set_progress(self, current: int, total: int):

        if total <= 0:
            self.progress_bar.setRange(0, 0)
            return

        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)

    def update_buttons(self):

        busy = self._task is not None

        self.scan_button.setEnabled(not busy)
        self.import_button.setEnabled(not busy)
        self.save_button.setEnabled(
            not busy and self.snapshot is not None
        )
        self.restore_button.setEnabled(
            not busy
            and self.report is not None
            and self.report.has_restorable_items
        )

    # ==================================================
    # SCAN PC
    # ==================================================

    def scan_pc(self):

        if self._task is not None:
            return

        self._start_scan(mode="scan")

    def _start_scan(self, mode: str = "scan"):

        self._scan_mode = mode

        if mode == "import":
            self._set_status("Checking your current environment...")
        else:
            self._set_status("Scanning your PC...")

        self._start_task("scan", self._scan_job)

    def _scan_job(self, reporter):

        reporter.set_progress(0, 0)

        scan_service = EnvironmentScanService(
            application_scanners=self.create_scanners()
        )

        return scan_service.scan(report=reporter.set_text)

    def _handle_scan_result(self, snapshot: EnvironmentSnapshot):

        self.snapshot = snapshot
        self.scan_results = list(snapshot.applications)

        errors = snapshot.errors

        if self._scan_mode == "import" and self.current_setup:

            compare_service = EnvironmentCompareService()

            self.report = compare_service.compare(
                self.current_setup,
                snapshot,
            )
            self.comparison = list(self.report.applications)

            self.result_title.setText(
                f"Imported Setup: {self.current_setup.name}"
            )

            self.show_report(self.report)

            if self._restore_outcome == "ok":
                self.result_title.setText(
                    "Setup restored successfully!"
                )
                self._set_status("Setup restored successfully.")

            elif self._restore_outcome == "errors":
                self.result_title.setText(
                    "Restore completed with errors"
                )
                self._set_status("Restore completed with errors.")

            else:
                version_note = ""

                if self.current_setup.format_version < 2:
                    version_note = (
                        " Version 1 setup: only applications "
                        "were saved."
                    )

                if self.report.has_restorable_items:
                    self._set_status(
                        "Setup imported. "
                        f"{self.report.restorable_item_count} "
                        f"difference(s) found.{version_note}"
                    )

                else:
                    self._set_status(
                        "Setup imported. Everything matches."
                        f"{version_note}"
                    )

            self._restore_outcome = None

        else:

            self.report = None
            self.comparison = []

            self.show_snapshot(snapshot)

            self.result_title.setText(
                "Your Development Environment"
            )

            self._set_status("Scan complete.")

        self.update_buttons()

        if errors:

            error_text = "\n".join(
                f"• {error}" for error in errors
            )

            QMessageBox.warning(
                self,
                "Scan warnings",
                "Some scanners reported problems:\n\n"
                f"{error_text}",
            )

    # ==================================================
    # SAVE SETUP
    # ==================================================

    def save_setup(self):

        if self._task is not None:
            return

        if self.snapshot is None:

            QMessageBox.information(
                self,
                "Save Setup",
                "Run Scan PC first so DevSetup knows "
                "what is installed.",
            )

            return

        default_name = (
            self.current_setup.name
            if self.current_setup
            else ""
        )

        name, ok = QInputDialog.getText(
            self,
            "Save Setup",
            "Setup name:",
            text=default_name,
        )

        if not ok:
            return

        name = name.strip()

        if not name:

            QMessageBox.warning(
                self,
                "Save Setup",
                "Setup name cannot be empty.",
            )

            return

        default_path = os.path.join(
            os.path.expanduser("~"),
            f"{name}.setup",
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Setup",
            default_path,
            "DevSetup (*.setup)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".setup"):
            file_path += ".setup"

        setup = Setup.from_snapshot(
            name=name,
            snapshot=self.snapshot,
        )

        try:
            SetupExporter().export(
                setup=setup,
                output_path=file_path,
            )

        except OSError as error:

            QMessageBox.critical(
                self,
                "Save Error",
                "Could not save the setup file:\n\n"
                f"{error}",
            )

            return

        self._set_status(f"Setup saved to {file_path}")

        QMessageBox.information(
            self,
            "DevSetup",
            "Setup saved successfully!\n\n"
            f"{file_path}",
        )

    # ==================================================
    # IMPORT SETUP
    # ==================================================

    def import_setup(self):

        if self._task is not None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Setup",
            os.path.expanduser("~"),
            "DevSetup (*.setup);;All files (*)",
        )

        if not file_path:
            return

        try:
            setup = SetupImporter().import_setup(
                file_path
            )

        except (OSError, ValueError) as error:

            QMessageBox.critical(
                self,
                "Import Error",
                str(error),
            )

            return

        self.current_setup = setup
        self.report = None
        self.comparison = []
        self.snapshot = None
        self.scan_results = []

        self.set_placeholder(
            "Checking your current environment..."
        )

        self.result_title.setText(
            f"Imported Setup: {setup.name}"
        )

        self.update_buttons()

        self._start_scan(mode="import")

    # ==================================================
    # RESTORE SETUP
    # ==================================================

    def restore_setup(self):

        if self._task is not None or self.report is None:
            return

        if not self.report.has_restorable_items:

            QMessageBox.information(
                self,
                "DevSetup",
                "Everything saved in this setup is already "
                "installed.",
            )

            self._set_status(
                "Everything is already installed."
            )

            return

        dialog = RestoreDialog(self.report, self)

        if dialog.exec() != QDialog.Accepted:
            self._set_status("Restore cancelled.")
            return

        selection = dialog.selection()

        if selection.is_empty:
            self._set_status("Restore cancelled.")
            return

        answer = QMessageBox.question(
            self,
            "Restore Setup",
            self._confirmation_text(selection),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            self._set_status("Restore cancelled.")
            return

        self._restore_outcome = None

        self._set_status(
            f"Restoring {selection.step_count} item(s)..."
        )

        self._start_task(
            "restore",
            lambda reporter: EnvironmentRestoreService().run(
                selection,
                reporter,
            ),
        )

    def _confirmation_text(
        self,
        selection: RestoreSelection,
    ) -> str:
        lines = [
            (
                f"Restore {selection.step_count} item(s) in "
                f"{selection.category_count} category(ies)?"
            ),
            "",
        ]

        if selection.applications:
            lines.append(
                f"• Applications: "
                f"{len(selection.applications)}"
            )

        if selection.version_restores:
            lines.append(
                f"• Version changes: "
                f"{len(selection.version_restores)}"
            )

        if selection.extensions:
            lines.append(
                f"• VS Code extensions: "
                f"{len(selection.extensions)}"
            )

        if selection.python_packages:
            lines.append(
                f"• Python packages: "
                f"{len(selection.python_packages)}"
            )

        if selection.npm_packages:
            lines.append(
                f"• npm packages: "
                f"{len(selection.npm_packages)}"
            )

        if selection.git_config:
            lines.append(
                f"• Git settings: "
                f"{len(selection.git_config)}"
            )

        if selection.environment_variables:
            lines.append(
                f"• Environment variables: "
                f"{len(selection.environment_variables)}"
            )

        if selection.wsl_distributions:
            lines.append(
                f"• WSL distributions: "
                f"{len(selection.wsl_distributions)}"
            )

        lines.extend(
            [
                "",
                "DevSetup will only perform the selected steps. "
                "Continue?",
            ]
        )

        return "\n".join(lines)

    def _handle_restore_result(self, result: RestoreResult):

        failed = result.failed

        if failed:

            failure_text = "\n".join(
                f"• {item.label}: {item.message}"
                for item in failed[:_MAX_PREVIEW_LINES]
            )

            if len(failed) > _MAX_PREVIEW_LINES:
                failure_text += (
                    f"\n… and {len(failed) - _MAX_PREVIEW_LINES} "
                    "more."
                )

            QMessageBox.warning(
                self,
                "Restore completed with errors",
                "Some items could not be restored:\n\n"
                f"{failure_text}",
            )

            self._restore_outcome = "errors"

            self._set_status(
                f"Restore finished: {len(result.succeeded)} "
                f"succeeded, {len(failed)} failed."
            )

        else:

            QMessageBox.information(
                self,
                "Restore completed",
                "Development environment has been "
                "restored successfully!\n\n"
                f"{result.total} item(s) restored.",
            )

            self._restore_outcome = "ok"

        # Rescan so the window shows the real state of the PC.
        self._start_scan(mode="import")

    # ==================================================
    # VERSION RESTORE
    # ==================================================

    def _restore_version(self, item):
        """Handle the [Restore Version] button of one application card."""

        if self._task is not None:
            return

        saved = item.saved

        answer = QMessageBox.question(
            self,
            "Restore Version",
            f"{saved.name}\n"
            f"Saved: {saved.version}\n"
            f"Current: {item.current_version}\n\n"
            "DevSetup will ask winget to install the saved "
            "version. If winget does not have this exact version, "
            "nothing will be installed.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            self._set_status("Version restore cancelled.")
            return

        self._set_status(
            f"Restoring {saved.name} {saved.version}..."
        )

        self._start_task(
            "version",
            lambda reporter: self._version_job(
                reporter,
                saved,
            ),
        )

    def _version_job(self, reporter, application):

        reporter.set_progress(0, 0)
        reporter.set_text(
            f"Restoring {application.name} "
            f"{application.version}..."
        )

        service = RestoreService()

        return service.install_version(
            application,
            application.version,
        )

    def _handle_version_result(self, result):

        success, message = result

        if success:
            QMessageBox.information(
                self,
                "Restore Version",
                message,
            )

            self._start_scan(mode="import")

        else:
            QMessageBox.warning(
                self,
                "Restore Version",
                message,
            )

            self._set_status(
                f"Version restore failed: {message}"
            )

    # ==================================================
    # RENDERING HELPERS
    # ==================================================

    def clear_results(self):

        while self.results_layout.count():

            item = self.results_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def add_section(self, title: str):

        label = QLabel(title)
        label.setObjectName("Section")
        self.results_layout.addWidget(label)

    def add_note(self, text: str):

        label = QLabel(text)
        label.setObjectName("CardMeta")
        label.setWordWrap(True)
        self.results_layout.addWidget(label)

    def set_placeholder(self, text: str):

        self.clear_results()

        label = QLabel(text)
        label.setObjectName("Placeholder")
        label.setWordWrap(True)

        self.results_layout.addWidget(label)
        self.results_layout.addStretch(1)

    def add_preview_lines(
        self,
        lines: list[str],
        prefix: str = "• ",
    ) -> list[str]:
        preview = [
            f"{prefix}{line}"
            for line in lines[:_MAX_PREVIEW_LINES]
        ]

        if len(lines) > _MAX_PREVIEW_LINES:
            preview.append(
                f"… and {len(lines) - _MAX_PREVIEW_LINES} more."
            )

        return preview

    # ==================================================
    # SHOW SCANNED ENVIRONMENT
    # ==================================================

    def show_snapshot(self, snapshot: EnvironmentSnapshot):

        self.clear_results()

        self.add_section("Applications")

        if not snapshot.applications:
            self.add_note(
                "Nothing was found. Click Scan PC to try again."
            )

        for application in snapshot.applications:

            card = ApplicationCard(
                name=application.name,
                version=application.version,
                path=application.path,
                installed=application.installed,
            )

            self.results_layout.addWidget(card)

        self.show_extensions_snapshot(snapshot)
        self.show_packages_snapshot(snapshot)
        self.show_configuration_snapshot(snapshot)
        self.show_wsl_snapshot(snapshot)

        self.add_section("Terminal")
        self.results_layout.addWidget(
            SummaryCard(
                "Windows Terminal",
                self._terminal_lines(snapshot.terminal),
                status="Read-only",
            )
        )

        self.results_layout.addStretch(1)

    def show_extensions_snapshot(
        self,
        snapshot: EnvironmentSnapshot,
    ):
        self.add_section("VS Code Extensions")

        extensions = snapshot.vscode_extensions

        if not snapshot.capabilities.get("vscode", False):
            lines = ["VS Code is not installed."]
            status = "Unavailable"

        elif not extensions:
            lines = ["No extensions installed."]
            status = "0 installed"

        else:
            lines = self.add_preview_lines(extensions)
            status = f"{len(extensions)} installed"

        self.results_layout.addWidget(
            SummaryCard(
                "VS Code extensions",
                lines,
                status=status,
            )
        )

    def show_packages_snapshot(
        self,
        snapshot: EnvironmentSnapshot,
    ):
        self.add_section("Packages")

        python_packages = snapshot.python_packages

        if not snapshot.capabilities.get("python", False):
            python_lines = ["Python is not installed."]
            python_status = "Unavailable"

        elif not python_packages:
            python_lines = ["No global packages found."]
            python_status = "0 packages"

        else:
            python_lines = self.add_preview_lines(
                python_packages
            )
            python_status = f"{len(python_packages)} packages"

        self.results_layout.addWidget(
            SummaryCard(
                "Python global packages",
                python_lines,
                status=python_status,
            )
        )

        npm_packages = snapshot.npm_packages

        if not snapshot.capabilities.get("npm", False):
            npm_lines = ["npm is not installed."]
            npm_status = "Unavailable"

        elif not npm_packages:
            npm_lines = ["No global packages found."]
            npm_status = "0 packages"

        else:
            npm_lines = self.add_preview_lines(npm_packages)
            npm_status = f"{len(npm_packages)} packages"

        self.results_layout.addWidget(
            SummaryCard(
                "npm global packages",
                npm_lines,
                status=npm_status,
            )
        )

    def show_configuration_snapshot(
        self,
        snapshot: EnvironmentSnapshot,
    ):
        self.add_section("Configuration")

        git_config = snapshot.git_config

        if not snapshot.capabilities.get("git", False):
            git_lines = ["Git is not installed."]
            git_status = "Unavailable"

        elif not git_config:
            git_lines = ["No safe Git settings found."]
            git_status = "0 settings"

        else:
            git_lines = self.add_preview_lines(
                [
                    f"{key} = {_preview(value)}"
                    for key, value in git_config.items()
                ]
            )
            git_status = f"{len(git_config)} settings"

        self.results_layout.addWidget(
            SummaryCard(
                "Git configuration",
                git_lines,
                status=git_status,
            )
        )

        environment_lines = [
            f"{name} = {_preview(value)}"
            for name, value in (
                snapshot.environment_variables.items()
            )
        ]

        environment_lines.extend(
            f"{name} — Secret — not backed up"
            for name in snapshot.secret_environment_variables
        )

        self.results_layout.addWidget(
            SummaryCard(
                "Environment variables",
                self.add_preview_lines(environment_lines)
                if environment_lines
                else ["No user environment variables found."],
                status=(
                    f"{len(snapshot.environment_variables)} saved"
                ),
            )
        )

    def show_wsl_snapshot(
        self,
        snapshot: EnvironmentSnapshot,
    ):
        self.add_section("WSL")

        if not snapshot.capabilities.get("wsl", False):
            lines = ["WSL is not installed."]
            status = "Unavailable"

        elif not snapshot.wsl_distributions:
            lines = ["No WSL distributions found."]
            status = "0 distributions"

        else:
            lines = [
                f"{distribution.name} — "
                f"WSL {distribution.version or '?'}"
                + (
                    f" — {distribution.state}"
                    if distribution.state
                    else ""
                )
                for distribution in snapshot.wsl_distributions
            ]
            status = f"{len(snapshot.wsl_distributions)} found"

        self.results_layout.addWidget(
            SummaryCard(
                "WSL distributions",
                lines,
                status=status,
            )
        )

    # ==================================================
    # SHOW COMPARISON
    # ==================================================

    def show_report(self, report: ComparisonReport):

        self.clear_results()

        self.add_section("Applications")

        if not report.applications:
            self.add_note(
                "This setup file does not contain any "
                "applications."
            )

        for item in report.applications:

            saved = item.saved

            version_text = (
                f"Saved: {saved.version}   |   "
                f"Current: {item.current_version}"
            )

            action_text = None
            action_callback = None

            if item.status is ComparisonStatus.VERSION_MISMATCH:
                action_text = "Restore Version"
                action_callback = (
                    lambda item=item: self._restore_version(item)
                )

            card = ApplicationCard(
                name=saved.name,
                version=saved.version,
                path=item.current_path,
                installed=not item.is_missing,
                status=item.status,
                action_text=action_text,
                action_callback=action_callback,
                version_label=version_text,
            )

            self.results_layout.addWidget(card)

        self.show_extensions_report(report)
        self.show_packages_report(report)
        self.show_configuration_report(report)
        self.show_wsl_report(report)

        self.add_section("Terminal")
        self.results_layout.addWidget(
            SummaryCard(
                "Windows Terminal",
                self._terminal_lines(report.terminal),
                status="Read-only",
            )
        )

        self.results_layout.addStretch(1)

    def show_extensions_report(self, report: ComparisonReport):
        comparison = report.extensions

        if not comparison.saved:
            return

        self.add_section("VS Code Extensions")

        if not report.snapshot.capabilities.get("vscode", False):
            status = "VS Code not installed"
            color = "#cf222e"

        elif comparison.in_sync:
            status = "✓ In sync"
            color = "#1a7f37"

        else:
            status = f"✗ {len(comparison.missing)} missing"
            color = "#cf222e"

        lines = [
            f"Saved: {len(comparison.saved)}   |   "
            f"Current: {len(comparison.current)}"
        ]

        lines.extend(
            self.add_preview_lines(
                [
                    f"Missing: {extension_id}"
                    for extension_id in comparison.missing
                ]
            )
        )

        self.results_layout.addWidget(
            SummaryCard(
                "VS Code extensions",
                lines,
                status=status,
                status_color=color,
            )
        )

    def show_packages_report(self, report: ComparisonReport):
        python = report.python_packages
        npm = report.npm_packages

        if not python.saved and not npm.saved:
            return

        self.add_section("Packages")

        if python.saved:
            lines = [
                f"Saved: {len(python.saved)}   |   "
                f"Current: {len(python.current)}"
            ]

            lines.extend(
                self.add_preview_lines(
                    [
                        f"Missing: {requirement.raw}"
                        for requirement in python.missing
                    ]
                )
            )

            lines.extend(
                self.add_preview_lines(
                    [
                        f"Different version: {requirement.raw}"
                        for requirement in python.mismatched
                    ]
                )
            )

            self.results_layout.addWidget(
                SummaryCard(
                    "Python global packages",
                    lines,
                    status=(
                        "✓ In sync"
                        if python.in_sync
                        else (
                            f"✗ {python.difference_count} "
                            "difference(s)"
                        )
                    ),
                    status_color=(
                        "#1a7f37"
                        if python.in_sync
                        else "#cf222e"
                    ),
                )
            )

        if npm.saved:
            lines = [
                f"Saved: {len(npm.saved)}   |   "
                f"Current: {len(npm.current)}"
            ]

            lines.extend(
                self.add_preview_lines(
                    [
                        f"Missing: {requirement.name}"
                        for requirement in npm.missing
                    ]
                )
            )

            if not report.snapshot.capabilities.get(
                "npm",
                False,
            ):
                lines.append("npm is not installed.")
                npm_status = "Unavailable"
                npm_color = "#8c959f"

            elif npm.in_sync:
                npm_status = "✓ In sync"
                npm_color = "#1a7f37"

            else:
                npm_status = f"✗ {npm.difference_count} missing"
                npm_color = "#cf222e"

            self.results_layout.addWidget(
                SummaryCard(
                    "npm global packages",
                    lines,
                    status=npm_status,
                    status_color=npm_color,
                )
            )

    def show_configuration_report(
        self,
        report: ComparisonReport,
    ):
        git_config = report.git_config
        environment = report.environment

        if (
            not git_config.saved
            and not environment.saved
            and not environment.secrets
        ):
            return

        self.add_section("Configuration")

        if git_config.saved:
            lines = []

            lines.extend(
                f"Missing: {key} = {_preview(value)}"
                for key, value in git_config.missing.items()
            )

            lines.extend(
                f"Different: {key} ({_preview(current)} → "
                f"{_preview(saved)})"
                for key, (
                    saved,
                    current,
                ) in git_config.mismatched.items()
            )

            self.results_layout.addWidget(
                SummaryCard(
                    "Git configuration",
                    lines or ["✓ Matches the setup."],
                    status=(
                        "✓ In sync"
                        if git_config.in_sync
                        else (
                            f"✗ {git_config.difference_count} "
                            "difference(s)"
                        )
                    ),
                    status_color=(
                        "#1a7f37"
                        if git_config.in_sync
                        else "#cf222e"
                    ),
                )
            )

        if environment.saved or environment.secrets:
            lines = []

            lines.extend(
                f"Missing: {name} = "
                f"{_preview(environment.saved[name])}"
                for name in environment.missing
            )

            lines.extend(
                f"Different: {name} ({_preview(current)} → "
                f"{_preview(saved)})"
                for name, saved, current in (
                    environment.mismatched
                )
            )

            lines.extend(
                f"{name} — Secret — not backed up"
                for name in environment.secrets
            )

            self.results_layout.addWidget(
                SummaryCard(
                    "Environment variables",
                    lines or ["✓ Matches the setup."],
                    status=(
                        "✓ In sync"
                        if environment.in_sync
                        else (
                            f"✗ {environment.difference_count} "
                            "difference(s)"
                        )
                    ),
                    status_color=(
                        "#1a7f37"
                        if environment.in_sync
                        else "#cf222e"
                    ),
                )
            )

    def show_wsl_report(self, report: ComparisonReport):
        comparison = report.wsl

        if not comparison.saved:
            return

        self.add_section("WSL")

        missing_names = {
            distribution.name.lower()
            for distribution in comparison.missing
        }

        current_by_name = {
            distribution.name.lower(): distribution
            for distribution in comparison.current
        }

        for distribution in comparison.saved:
            key = distribution.name.lower()
            current = current_by_name.get(key)
            installed = key not in missing_names

            lines = [
                f"Saved: WSL {distribution.version or '?'}"
            ]

            if installed and current is not None:
                lines.append(
                    f"Current: WSL {current.version or '?'}"
                )

                if current.state:
                    lines.append(f"State: {current.state}")

                status = "✓ Installed"
                color = "#1a7f37"

            else:
                lines.append("Current: Missing")
                status = "✗ Missing"
                color = "#cf222e"

            self.results_layout.addWidget(
                SummaryCard(
                    distribution.name,
                    lines,
                    status=status,
                    status_color=color,
                )
            )

    # ==================================================
    # COMPATIBILITY RENDERERS
    # ==================================================

    def show_applications(self, applications):

        self.clear_results()

        if not applications:

            self.set_placeholder(
                "Nothing was found. Click Scan PC to try again."
            )

            return

        for application in applications:

            card = ApplicationCard(
                name=application.name,
                version=application.version,
                path=application.path,
                installed=application.installed,
            )

            self.results_layout.addWidget(card)

        self.results_layout.addStretch(1)

    def show_comparison(self, comparison):

        self.clear_results()

        if not comparison:

            self.set_placeholder(
                "This setup file does not contain "
                "any applications."
            )

            return

        for item in comparison:

            saved = item.saved

            version_text = (
                f"Saved: {saved.version}   |   "
                f"Current: {item.current_version}"
            )

            card = ApplicationCard(
                name=saved.name,
                version=saved.version,
                path=item.current_path,
                installed=not item.is_missing,
                status=item.status,
                version_label=version_text,
            )

            self.results_layout.addWidget(card)

        self.results_layout.addStretch(1)

    # ==================================================
    # MISC
    # ==================================================

    def _terminal_lines(
        self,
        terminal: TerminalSettings,
    ) -> list[str]:
        if not terminal.available:
            return [
                terminal.message
                or "Windows Terminal settings were not detected."
            ]

        lines = []

        if terminal.default_profile:
            lines.append(
                f"Default profile: {terminal.default_profile}"
            )

        if terminal.profiles:
            lines.append(
                "Profiles: " + ", ".join(terminal.profiles[:10])
            )

        if terminal.font_face:
            lines.append(f"Font: {terminal.font_face}")

        if terminal.color_scheme:
            lines.append(
                f"Color scheme: {terminal.color_scheme}"
            )

        if not lines:
            lines.append("Windows Terminal settings were found.")

        return lines

    def closeEvent(self, event):

        if self._task is not None and self._task.isRunning():

            QMessageBox.information(
                self,
                "DevSetup",
                "Please wait for the current operation "
                "to finish.",
            )

            event.ignore()
            return

        super().closeEvent(event)
