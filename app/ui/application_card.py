from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.models.comparison import ComparisonStatus

_STATUS_TEXT = {
    ComparisonStatus.INSTALLED: ("✓ Installed", "#1a7f37"),
    ComparisonStatus.MISSING: ("✗ Missing", "#cf222e"),
    ComparisonStatus.VERSION_MISMATCH: (
        "⚠ Version mismatch",
        "#9a6700",
    ),
}


class ApplicationCard(QFrame):

    def __init__(
        self,
        name: str,
        version: str,
        path: str | None,
        installed: bool,
        status: ComparisonStatus | None = None,
        action_text: str | None = None,
        action_callback=None,
        version_label: str | None = None,
    ):
        super().__init__()

        self.setObjectName("Card")
        self._action_callback = action_callback
        self.action_button = None

        self.setup_ui(
            name=name,
            version=version,
            path=path,
            installed=installed,
            status=status,
            action_text=action_text,
            version_label=version_label,
        )

    def setup_ui(
        self,
        name: str,
        version: str,
        path: str | None,
        installed: bool,
        status: ComparisonStatus | None,
        action_text: str | None,
        version_label: str | None,
    ):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(name)
        title.setObjectName("CardTitle")

        if status is not None:
            status_text, status_color = _STATUS_TEXT[status]

        elif installed:
            status_text, status_color = "✓ Installed", "#1a7f37"

        else:
            status_text, status_color = "✗ Not installed", "#8c959f"

        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            f"color: {status_color}; font-weight: 600;"
        )

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(status_label)

        version_text = (
            version_label
            if version_label is not None
            else f"Version: {version}"
        )

        version_label_widget = QLabel(version_text)
        version_label_widget.setWordWrap(True)

        path_label = QLabel(
            f"Path: {path if path else 'Not found'}"
        )
        path_label.setObjectName("CardMeta")
        path_label.setWordWrap(True)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(path_label, 1)

        if action_text:
            self.action_button = QPushButton(action_text)
            self.action_button.clicked.connect(self._on_action)
            footer.addWidget(self.action_button)

        layout.addLayout(header)
        layout.addWidget(version_label_widget)
        layout.addLayout(footer)

    def _on_action(self):
        if self._action_callback is not None:
            self._action_callback()
