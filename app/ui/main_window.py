from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("DevSetup")
        self.resize(900, 600)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        title = QLabel("DevSetup")
        title.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
        """)

        description = QLabel(
            "Backup and restore your development environment."
        )

        scan_button = QPushButton("Scan PC")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(scan_button)
        layout.addStretch()