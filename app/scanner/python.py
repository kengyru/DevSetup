import shutil

from app.core.packages import get_package_id
from app.core.versions import extract_version
from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner
from app.scanner.command import ScannerError, run_command


class PythonScanner(BaseScanner):

    NAME = "Python"
    PACKAGE_ID = get_package_id(NAME)

    def scan(self) -> InstalledApplication:
        python_path = shutil.which("python")

        if not python_path:
            python_path = shutil.which("python3")

        if not python_path:
            return self.missing()

        try:
            output = run_command(python_path, ["--version"])
            version = extract_version(output) or output

        except ScannerError:
            version = "Unknown"

        return InstalledApplication(
            name=self.NAME,
            version=version,
            path=python_path,
            installed=True,
            package_id=self.PACKAGE_ID,
        )
