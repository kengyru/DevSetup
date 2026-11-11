from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)


class SummaryCard(QFrame):
    """A compact card for a category that has no per-item actions."""

    def __init__(
        self,
        title: str,
        lines: list[str] | None = None,
        status: str | None = None,
        status_color: str = "#57606a",
    ):
        super().__init__()

        self.setObjectName("Card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        header.addWidget(title_label)
        header.addStretch(1)

        if status:
            status_label = QLabel(status)
            status_label.setStyleSheet(
                f"color: {status_color}; font-weight: 600;"
            )
            header.addWidget(status_label)

        layout.addLayout(header)

        for line in lines or []:
            label = QLabel(line)
            label.setObjectName("CardMeta")
            label.setWordWrap(True)
            layout.addWidget(label)
