import shutil

from app.core.packages import get_package_id
from app.models.application import InstalledApplication
from app.scanner.base import BaseScanner
from app.scanner.command import ScannerError, run_command


class GitScanner(BaseScanner):

    NAME = "Git"
    PACKAGE_ID = get_package_id(NAME)

    def scan(self) -> InstalledApplication:
        git_path = shutil.which("git")

        if not git_path:
            return self.missing()

        try:
            output = run_command(git_path, ["--version"])
            version = output

        except ScannerError:
            version = "Unknown"

        return InstalledApplication(
            name=self.NAME,
            version=version,
            path=git_path,
            installed=True,
            package_id=self.PACKAGE_ID,
        )
