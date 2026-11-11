import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import MainWindow

STYLESHEET = """
QWidget {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
    color: #1f2328;
}

QWidget#Root {
    background-color: #f6f7f9;
}

QDialog {
    background-color: #f6f7f9;
}

QLabel#Title {
    font-size: 30px;
    font-weight: 700;
}

QLabel#Description {
    color: #57606a;
    font-size: 14px;
}

QLabel#Section {
    font-size: 18px;
    font-weight: 600;
    margin-top: 8px;
}

QLabel#Status {
    color: #57606a;
}

QLabel#Placeholder {
    color: #8c959f;
}

QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #d8dee4;
    border-radius: 10px;
}

QLabel#CardTitle {
    font-size: 16px;
    font-weight: 600;
}

QLabel#CardMeta {
    color: #6e7781;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollArea QWidget#qt_scrollarea_viewport {
    background: transparent;
}

QWidget#Cards {
    background: transparent;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton:hover {
    background-color: #f3f4f6;
}

QPushButton:pressed {
    background-color: #e9ebee;
}

QPushButton:disabled {
    color: #8c959f;
    background-color: #f6f8fa;
}

QPushButton#Primary {
    background-color: #1f6feb;
    border: 1px solid #1f6feb;
    color: #ffffff;
}

QPushButton#Primary:hover {
    background-color: #1a5fd0;
}

QPushButton#Primary:disabled {
    background-color: #a8c0e8;
    border-color: #a8c0e8;
    color: #f0f4fa;
}

QProgressBar {
    border: 1px solid #d0d7de;
    border-radius: 4px;
    background-color: #ffffff;
    max-height: 10px;
}

QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 3px;
}
"""


def install_excepthook() -> None:
    """Show unexpected errors instead of silently losing them."""

    def handle_exception(exc_type, exc_value, exc_tb):

        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(
                exc_type,
                exc_value,
                exc_tb,
            )
            return

        traceback.print_exception(
            exc_type,
            exc_value,
            exc_tb,
        )

        QMessageBox.critical(
            None,
            "DevSetup - Unexpected error",
            f"{exc_type.__name__}: {exc_value}",
        )

    sys.excepthook = handle_exception


def main():

    app = QApplication(sys.argv)
    app.setApplicationName("DevSetup")
    app.setApplicationDisplayName("DevSetup")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    install_excepthook()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
