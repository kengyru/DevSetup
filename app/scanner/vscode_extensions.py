from app.core.requirements import is_valid_extension_id
from app.scanner.base import BaseCollector
from app.scanner.command import run_command
from app.scanner.vscode import VSCodeScanner


class VSCodeExtensionsScanner(BaseCollector):
    """Lists installed VS Code extensions through `code --list-extensions`."""

    NAME = "VS Code extensions"

    def scan(self) -> list[str]:
        code_path = VSCodeScanner().find_path()

        if not code_path:
            self.available = False
            return []

        output = run_command(
            code_path,
            ["--list-extensions"],
            timeout=60,
        )

        extensions = set()

        for line in output.splitlines():
            extension_id = line.strip()

            if is_valid_extension_id(extension_id):
                extensions.add(extension_id.lower())

        return sorted(extensions)
