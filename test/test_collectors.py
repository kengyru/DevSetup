import unittest
from unittest import mock

from app.core.process import ProcessResult
from app.models.environment import TerminalSettings
from app.scanner.environment import EnvironmentScanner
from app.scanner.git_config import (
    GitConfigScanner,
    parse_git_config,
)
from app.scanner.npm_packages import parse_npm_output
from app.scanner.terminal import (
    parse_terminal_settings,
    strip_jsonc,
)
from app.scanner.vscode_extensions import VSCodeExtensionsScanner
from app.scanner.wsl import (
    decode_wsl_output,
    parse_wsl_list,
)


class VSCodeExtensionsScannerTests(unittest.TestCase):

    @mock.patch(
        "app.scanner.vscode_extensions.run_command",
        return_value=(
            "ms-python.python\n"
            "ms-azuretools.vscode-docker\n"
            "not an extension\n"
            "ms-python.python\n"
        ),
    )
    @mock.patch(
        "app.scanner.vscode_extensions.VSCodeScanner.find_path",
        return_value=r"C:\VSCode\bin\code.cmd",
    )
    def test_scan_filters_and_deduplicates(
        self,
        _find_path,
        run_command,
    ):
        scanner = VSCodeExtensionsScanner()

        result = scanner.scan()

        self.assertEqual(
            result,
            [
                "ms-azuretools.vscode-docker",
                "ms-python.python",
            ],
        )
        self.assertTrue(scanner.available)
        run_command.assert_called_once_with(
            r"C:\VSCode\bin\code.cmd",
            ["--list-extensions"],
            timeout=60,
        )

    @mock.patch(
        "app.scanner.vscode_extensions.VSCodeScanner.find_path",
        return_value=None,
    )
    def test_missing_vscode_is_reported(self, _find_path):
        scanner = VSCodeExtensionsScanner()

        self.assertEqual(scanner.scan(), [])
        self.assertFalse(scanner.available)


class GitConfigScannerTests(unittest.TestCase):

    def test_only_allowlisted_settings_are_kept(self):
        result = parse_git_config(
            "User.Name=Ann\n"
            "user.email=ann@example.test\n"
            "credential.helper=manager\n"
            "url.https://token@example.test=.insteadof\n"
            "core.editor=code --wait\n"
            "alias.lol=log --oneline\n"
        )

        self.assertEqual(
            result,
            {
                "user.name": "Ann",
                "user.email": "ann@example.test",
                "core.editor": "code --wait",
            },
        )

    @mock.patch(
        "app.scanner.git_config.run_process",
        return_value=ProcessResult(
            returncode=1,
            output="",
        ),
    )
    @mock.patch(
        "app.scanner.git_config.shutil.which",
        return_value=r"C:\Git\git.exe",
    )
    def test_missing_global_config_is_not_an_error(
        self,
        _which,
        _run,
    ):
        scanner = GitConfigScanner()

        self.assertEqual(scanner.scan(), {})
        self.assertTrue(scanner.available)

    @mock.patch(
        "app.scanner.git_config.shutil.which",
        return_value=None,
    )
    def test_missing_git_is_reported(self, _which):
        scanner = GitConfigScanner()

        self.assertEqual(scanner.scan(), {})
        self.assertFalse(scanner.available)


class NpmParserTests(unittest.TestCase):

    def test_json_output(self):
        output = (
            '{"dependencies": {'
            '"typescript": {"version": "5.6.3"},'
            '"npm-check-updates": {"version": "17.1.0"}'
            "}}"
        )

        self.assertEqual(
            parse_npm_output(output),
            ["npm-check-updates", "typescript"],
        )

    def test_text_output(self):
        output = (
            "C:\\Users\\dev\\AppData\\Roaming\\npm\n"
            "+-- typescript@5.6.3\n"
            "+-- npm-check-updates@17.1.0\n"
            "`-- @scope/pkg@1.0.0\n"
        )

        self.assertEqual(
            parse_npm_output(output),
            ["@scope/pkg", "npm-check-updates", "typescript"],
        )

    def test_garbage_is_ignored(self):
        self.assertEqual(parse_npm_output("no packages here"), [])


class WSLParserTests(unittest.TestCase):

    def test_utf16_output_is_decoded(self):
        text = "* Ubuntu Running 2\r\n"

        self.assertEqual(
            decode_wsl_output(text.encode("utf-16-le")),
            text,
        )

    def test_utf16_bom_is_decoded(self):
        text = "  Debian Stopped 1\r\n"

        self.assertEqual(
            decode_wsl_output(
                b"\xff\xfe" + text.encode("utf-16-le")
            ),
            text,
        )

    def test_list_parsing_skips_localized_header(self):
        distributions = parse_wsl_list(
            "  NAME      STATE           VERSION\n"
            "* Ubuntu    Running         2\n"
            "  Debian    Stopped         1\n"
        )

        self.assertEqual(
            [distribution.name for distribution in distributions],
            ["Ubuntu", "Debian"],
        )
        self.assertEqual(distributions[0].version, 2)
        self.assertEqual(distributions[0].state, "Running")
        self.assertEqual(distributions[1].version, 1)


class TerminalParserTests(unittest.TestCase):

    def test_jsonc_comments_and_trailing_commas(self):
        text = """
        {
            // Windows Terminal allows comments
            "defaultProfile": "{ubuntu}",
            /* and block comments */
            "profiles": {
                "defaults": {
                    "font": {"face": "Cascadia Code"},
                    "colorScheme": "Campbell",
                },
                "list": [
                    {"guid": "{ubuntu}", "name": "Ubuntu"},
                    {"guid": "{pwsh}", "name": "PowerShell"},
                ],
            },
        }
        """

        settings = parse_terminal_settings(
            strip_jsonc(text),
            r"C:\settings.json",
        )

        self.assertTrue(settings.available)
        self.assertEqual(settings.default_profile, "Ubuntu")
        self.assertEqual(
            settings.profiles,
            ["Ubuntu", "PowerShell"],
        )
        self.assertEqual(settings.font_face, "Cascadia Code")
        self.assertEqual(settings.color_scheme, "Campbell")

    def test_missing_profiles_does_not_crash(self):
        settings = parse_terminal_settings("{}", "settings.json")

        self.assertTrue(settings.available)
        self.assertIsNone(settings.default_profile)
        self.assertEqual(settings.profiles, [])

    def test_invalid_json_still_raises(self):
        with self.assertRaises(ValueError):
            parse_terminal_settings("{not json", "settings.json")


class EnvironmentScannerTests(unittest.TestCase):

    @mock.patch(
        "app.scanner.environment._read_user_values",
        return_value=[
            ("EDITOR", "code --wait", 1),
            ("OPENAI_API_KEY", "sk-test", 1),
            ("GITHUB_TOKEN", "ghp_test", 1),
            ("Path", r"C:\Windows", 1),
            ("BAD NAME", "x", 1),
        ],
    )
    def test_secrets_are_listed_but_not_saved(self, _read):
        scanner = EnvironmentScanner()

        saved = scanner.scan()

        self.assertEqual(saved, {"EDITOR": "code --wait"})
        self.assertEqual(
            scanner.secrets,
            ["GITHUB_TOKEN", "OPENAI_API_KEY"],
        )

    @mock.patch(
        "app.scanner.environment.winreg",
        None,
    )
    def test_non_windows_is_reported(self):
        scanner = EnvironmentScanner()

        self.assertEqual(scanner.scan(), {})
        self.assertFalse(scanner.available)


class TerminalSettingsModelTests(unittest.TestCase):

    def test_dict_round_trip(self):
        settings = TerminalSettings(
            available=True,
            settings_path=r"C:\settings.json",
            default_profile="PowerShell",
            profiles=["PowerShell"],
            font_face="Cascadia Mono",
            color_scheme="One Half Dark",
        )

        restored = TerminalSettings.from_dict(settings.to_dict())

        self.assertEqual(restored, settings)

    def test_invalid_section_is_rejected(self):
        with self.assertRaises(ValueError):
            TerminalSettings.from_dict("nope")


if __name__ == "__main__":
    unittest.main()
