import traceback

from PySide6.QtCore import QThread, Signal


class TaskReporter:
    """Passed to a task job so it can update the window while it works."""

    def __init__(self, message_signal, progress_signal):
        self._message_signal = message_signal
        self._progress_signal = progress_signal

    def set_text(self, text: str) -> None:
        self._message_signal.emit(text)

    def set_progress(self, current: int, total: int) -> None:
        """Report progress. ``total <= 0`` means "work in progress"."""

        self._progress_signal.emit(int(current), int(total))


class Task(QThread):
    """Runs a long operation outside the UI thread.

    The job receives a TaskReporter and returns its result. It always ends
    with a single ``done(result, error)`` signal, so the window never has to
    guess whether a task succeeded and never crashes on exceptions.
    """

    message = Signal(str)
    progress = Signal(int, int)
    done = Signal(object, object)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        reporter = TaskReporter(
            self.message,
            self.progress,
        )

        result = None
        error = None

        try:
            result = self._job(reporter)

        except Exception as exception:
            traceback.print_exc()
            error = str(exception) or exception.__class__.__name__

        self.done.emit(result, error)
