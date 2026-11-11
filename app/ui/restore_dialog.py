from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models.comparison import (
    ComparisonReport,
    ComparisonStatus,
)
from app.models.restore import (
    RestoreSelection,
    VersionRestoreItem,
)


def _value_preview(value: str, limit: int = 100) -> str:
    text = value.replace("\r", " ").replace("\n", " ")

    if len(text) > limit:
        return text[: limit - 3] + "..."

    return text


class RestoreDialog(QDialog):
    """Lets the user tick exactly what should be restored.

    Nothing is executed here. The window only builds a RestoreSelection,
    and only when the user presses "Restore Selected".
    """

    def __init__(
        self,
        report: ComparisonReport,
        parent=None,
    ):
        super().__init__(parent)

        self.report = report

        self._application_boxes: list[tuple[QCheckBox, object]] = []
        self._version_boxes: list[tuple[QCheckBox, object]] = []
        self._wsl_boxes: list[tuple[QCheckBox, object]] = []

        self._extension_box = None
        self._python_box = None
        self._npm_box = None
        self._git_box = None
        self._environment_box = None

        self._all_boxes: list[QCheckBox] = []

        self.setWindowTitle("Restore Setup")
        self.setModal(True)
        self.setMinimumSize(680, 640)

        self.setup_ui()
        self.update_summary()

    # ==================================================
    # UI
    # ==================================================

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Restore Setup")
        title.setObjectName("Title")
        layout.addWidget(title)

        description = QLabel(
            "Choose what DevSetup should restore. Nothing is "
            "installed until you press Restore Selected."
        )
        description.setObjectName("Description")
        description.setWordWrap(True)
        layout.addWidget(description)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self.build_applications(content_layout)
        self.build_extensions(content_layout)
        self.build_packages(content_layout)
        self.build_configuration(content_layout)
        self.build_wsl(content_layout)
        self.build_terminal(content_layout)

        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)

        layout.addWidget(scroll, 1)

        self.summary_label = QLabel("0 item(s) selected.")
        self.summary_label.setObjectName("Status")
        layout.addWidget(self.summary_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        restore_button = QPushButton("Restore Selected")
        restore_button.setObjectName("Primary")
        restore_button.clicked.connect(self._on_accept)

        buttons.addWidget(cancel_button)
        buttons.addWidget(restore_button)

        layout.addLayout(buttons)

        for box in self._all_boxes:
            box.toggled.connect(self.update_summary)

    def add_heading(
        self,
        layout: QVBoxLayout,
        text: str,
    ) -> QVBoxLayout:
        heading = QLabel(text)
        heading.setObjectName("Section")
        layout.addWidget(heading)

        section = QVBoxLayout()
        section.setContentsMargins(8, 0, 0, 8)
        section.setSpacing(4)
        layout.addLayout(section)

        return section

    def add_checkbox(
        self,
        layout: QVBoxLayout,
        text: str,
        checked: bool = False,
        enabled: bool = True,
    ) -> QCheckBox:
        box = QCheckBox(text)
        box.setChecked(checked)
        box.setEnabled(enabled)
        box.setStyleSheet("font-weight: 600;")
        layout.addWidget(box)
        self._all_boxes.append(box)

        return box

    def add_note(
        self,
        layout: QVBoxLayout,
        text: str,
    ) -> None:
        label = QLabel(text)
        label.setObjectName("CardMeta")
        label.setWordWrap(True)
        layout.addWidget(label)

    # ==================================================
    # SECTIONS
    # ==================================================

    def build_applications(self, layout: QVBoxLayout):
        if not self.report.applications:
            return

        section = self.add_heading(layout, "Applications")
        action_items = [
            item
            for item in self.report.applications
            if item.status is not ComparisonStatus.INSTALLED
        ]

        if not action_items:
            self.add_note(
                section,
                "✓ All saved applications are installed.",
            )
            return

        for item in action_items:
            if item.status is ComparisonStatus.MISSING:
                box = self.add_checkbox(
                    section,
                    f"{item.name} — missing",
                    checked=True,
                )
                self._application_boxes.append((box, item))
                continue

            box = self.add_checkbox(
                section,
                (
                    f"{item.name} — restore version "
                    f"{item.saved.version} (current: "
                    f"{item.current_version})"
                ),
                checked=False,
            )
            self._version_boxes.append((box, item))

    def build_extensions(self, layout: QVBoxLayout):
        comparison = self.report.extensions

        if not comparison.saved:
            return

        section = self.add_heading(layout, "VS Code Extensions")

        if comparison.in_sync:
            self.add_note(section, "✓ All saved extensions are installed.")
            return

        self._extension_box = self.add_checkbox(
            section,
            f"Install {len(comparison.missing)} missing extension(s)",
            checked=True,
        )

        if not self.report.snapshot.capabilities.get(
            "vscode",
            False,
        ):
            self.add_note(
                section,
                "VS Code is not installed. Tick VS Code under "
                "Applications so extensions can be installed "
                "first; otherwise this step will fail.",
            )

        for extension_id in comparison.missing:
            self.add_note(section, f"• {extension_id}")

    def build_packages(self, layout: QVBoxLayout):
        python = self.report.python_packages
        npm = self.report.npm_packages

        if not python.saved and not npm.saved:
            return

        section = self.add_heading(layout, "Packages")

        if python.saved:
            if python.in_sync:
                self.add_note(
                    section,
                    "✓ Python packages are installed.",
                )
            else:
                self._python_box = self.add_checkbox(
                    section,
                    (
                        f"Install "
                        f"{python.difference_count} missing or "
                        "outdated Python package(s)"
                    ),
                    checked=True,
                )

                for requirement in python.missing:
                    self.add_note(section, f"• {requirement.raw}")

                for requirement in python.mismatched:
                    current = python.current_version_for(requirement)
                    self.add_note(
                        section,
                        f"• {requirement.raw} (current: "
                        f"{current or 'unknown'})",
                    )

                if not self.report.snapshot.capabilities.get(
                    "python",
                    False,
                ):
                    self.add_note(
                        section,
                        "Python is not installed; packages cannot "
                        "be restored.",
                    )

        if npm.saved:
            npm_available = bool(
                self.report.snapshot.capabilities.get(
                    "npm",
                    False,
                )
            )

            if npm.in_sync:
                self.add_note(
                    section,
                    "✓ npm global packages are installed.",
                )
            else:
                self._npm_box = self.add_checkbox(
                    section,
                    (
                        f"Install {npm.difference_count} missing "
                        "npm global package(s)"
                    ),
                    checked=npm_available,
                    enabled=npm_available,
                )

                for requirement in npm.missing:
                    self.add_note(section, f"• {requirement.name}")

                if not npm_available:
                    self.add_note(section, "npm is not installed.")

    def build_configuration(self, layout: QVBoxLayout):
        git_config = self.report.git_config
        environment = self.report.environment

        if not git_config.saved and not environment.saved:
            if not environment.secrets:
                return

        section = self.add_heading(layout, "Configuration")

        if git_config.saved:
            if git_config.in_sync:
                self.add_note(
                    section,
                    "✓ Git configuration matches the setup.",
                )
            else:
                self._git_box = self.add_checkbox(
                    section,
                    (
                        f"Restore {git_config.difference_count} "
                        "Git setting(s)"
                    ),
                    checked=True,
                )

                for key, value in git_config.missing.items():
                    self.add_note(
                        section,
                        f"• {key} = {_value_preview(value)}",
                    )

                for key, (saved, current) in (
                    git_config.mismatched.items()
                ):
                    self.add_note(
                        section,
                        f"• {key}: {_value_preview(current)} → "
                        f"{_value_preview(saved)}",
                    )

        if environment.saved:
            if environment.in_sync:
                self.add_note(
                    section,
                    "✓ Environment variables match the setup.",
                )
            else:
                self._environment_box = self.add_checkbox(
                    section,
                    (
                        f"Restore {environment.difference_count} "
                        "environment variable(s)"
                    ),
                    checked=False,
                )

                for name in environment.missing:
                    self.add_note(
                        section,
                        f"• {name} = "
                        f"{_value_preview(environment.saved[name])}",
                    )

                for name, saved, current in (
                    environment.mismatched
                ):
                    self.add_note(
                        section,
                        f"• {name}: {_value_preview(current)} → "
                        f"{_value_preview(saved)}",
                    )

        for name in environment.secrets:
            self.add_note(
                section,
                f"• {name} — Secret — not backed up",
            )

    def build_wsl(self, layout: QVBoxLayout):
        comparison = self.report.wsl

        if not comparison.saved:
            return

        section = self.add_heading(layout, "WSL")

        if comparison.in_sync:
            self.add_note(
                section,
                "✓ All saved WSL distributions are installed.",
            )
            return

        for distribution in comparison.missing:
            box = self.add_checkbox(
                section,
                (
                    f"{distribution.label} — missing "
                    "(installation may require UAC and a reboot)"
                ),
                checked=False,
                enabled=bool(
                    self.report.snapshot.capabilities.get(
                        "wsl",
                        False,
                    )
                ),
            )
            self._wsl_boxes.append((box, distribution))

        if not self.report.snapshot.capabilities.get(
            "wsl",
            False,
        ):
            self.add_note(section, "WSL is not installed.")

    def build_terminal(self, layout: QVBoxLayout):
        terminal = self.report.terminal

        section = self.add_heading(
            layout,
            "Terminal (read-only)",
        )

        if not terminal.available:
            self.add_note(
                section,
                terminal.message
                or "Windows Terminal settings were not detected.",
            )
            return

        self.add_note(
            section,
            "Detected only. DevSetup does not copy terminal "
            "settings between computers because profile GUIDs and "
            "paths are machine specific.",
        )

        if terminal.default_profile:
            self.add_note(
                section,
                f"Default profile: {terminal.default_profile}",
            )

        if terminal.profiles:
            self.add_note(
                section,
                "Profiles: " + ", ".join(terminal.profiles[:10]),
            )

        if terminal.font_face:
            self.add_note(
                section,
                f"Font: {terminal.font_face}",
            )

        if terminal.color_scheme:
            self.add_note(
                section,
                f"Color scheme: {terminal.color_scheme}",
            )

    # ==================================================
    # SELECTION
    # ==================================================

    def selection(self) -> RestoreSelection:
        selection = RestoreSelection()

        for box, item in self._application_boxes:
            if box.isChecked():
                selection.applications.append(item.saved)

        for box, item in self._version_boxes:
            if box.isChecked():
                selection.version_restores.append(
                    VersionRestoreItem(
                        application=item.saved,
                        version=item.saved.version,
                    )
                )

        if (
            self._extension_box is not None
            and self._extension_box.isChecked()
        ):
            selection.extensions = list(
                self.report.extensions.missing
            )

        if (
            self._python_box is not None
            and self._python_box.isChecked()
        ):
            selection.python_packages = [
                requirement.raw
                for requirement in (
                    self.report.python_packages.missing
                    + self.report.python_packages.mismatched
                )
            ]

        if self._npm_box is not None and self._npm_box.isChecked():
            selection.npm_packages = [
                requirement.name
                for requirement in self.report.npm_packages.missing
            ]

        if self._git_box is not None and self._git_box.isChecked():
            selection.git_config = {
                **self.report.git_config.missing,
                **{
                    key: saved
                    for key, (saved, _current) in (
                        self.report.git_config.mismatched.items()
                    )
                },
            }

        if (
            self._environment_box is not None
            and self._environment_box.isChecked()
        ):
            selection.environment_variables = {
                name: self.report.environment.saved[name]
                for name in self.report.environment.missing
            }

            for name, _saved, _current in (
                self.report.environment.mismatched
            ):
                selection.environment_variables[name] = (
                    self.report.environment.saved[name]
                )

        for box, distribution in self._wsl_boxes:
            if box.isChecked():
                selection.wsl_distributions.append(distribution)

        return selection

    def update_summary(self, *_args):
        count = self.selection().step_count
        self.summary_label.setText(
            f"{count} item(s) selected."
        )

    def _on_accept(self):
        if self.selection().is_empty:
            QMessageBox.information(
                self,
                "Restore Setup",
                "Select at least one item to restore.",
            )
            return

        self.accept()
