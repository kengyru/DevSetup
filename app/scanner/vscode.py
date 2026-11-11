import os
import shutil

from app.core.packages import get_package_id
from app.core.versions import extract_version
from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner
from app.scanner.command import ScannerError, run_command


class VSCodeScanner(BaseScanner):

    NAME = "VS Code"
    PACKAGE_ID = get_package_id(NAME)

    CANDIDATE_PATHS = (
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd"
        ),
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
    )

    def find_path(self) -> str | None:
        code_path = shutil.which("code")

        if code_path:
            return code_path

        for path in self.CANDIDATE_PATHS:
            if os.path.exists(path):
                return path

        return None

    def scan(self) -> InstalledApplication:
        code_path = self.find_path()

        if not code_path:
            return self.missing()

        try:
            output = run_command(code_path, ["--version"])
            first_line = output.splitlines()[0].strip()
            version = extract_version(first_line) or first_line

        except ScannerError:
            version = "Unknown"

        return InstalledApplication(
            name=self.NAME,
            version=version,
            path=code_path,
            installed=True,
            package_id=self.PACKAGE_ID,
        )
