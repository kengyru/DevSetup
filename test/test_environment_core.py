import unittest

from app.core.requirements import (
    is_valid_extension_id,
    is_valid_git_key,
    is_valid_npm_name,
    is_valid_wsl_name,
    parse_pip_freeze,
    parse_pip_requirement,
)
from app.core.secrets import (
    is_protected_name,
    is_safe_environment_name,
    is_secret_name,
)
from app.scanner.git_config import is_safe_git_key


class SecretDetectionTests(unittest.TestCase):

    def test_api_key_is_a_secret(self):
        self.assertTrue(is_secret_name("OPENAI_API_KEY"))

    def test_token_password_and_secret_are_detected(self):
        for name in (
            "GITHUB_TOKEN",
            "DB_PASSWORD",
            "APP_SECRET",
            "PRIVATE_KEY",
            "ACCESS_KEY",
            "AUTH_TOKEN",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_secret_name(name))

    def test_connection_string_is_a_secret(self):
        self.assertTrue(is_secret_name("DATABASE_CONNECTION_STRING"))

    def test_credential_bearing_urls_are_secrets(self):
        for name in (
            "DATABASE_URL",
            "MONGODB_URI",
            "REDIS_URL",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_secret_name(name))

    def test_key_suffixes_are_secrets(self):
        for name in ("STRIPE_KEY", "GPG_KEY", "DEPLOY_KEY"):
            with self.subTest(name=name):
                self.assertTrue(is_secret_name(name))

    def test_plain_urls_and_keyboard_settings_stay_safe(self):
        for name in (
            "PROJECT_URL",
            "API_URL",
            "KEYBOARD_LAYOUT",
            "DB_HOST",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_safe_environment_name(name))

    def test_normal_developer_variables_are_safe(self):
        for name in (
            "EDITOR",
            "NODE_OPTIONS",
            "PYTHONPATH",
            "JAVA_HOME",
            "GOPATH",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_safe_environment_name(name))

    def test_system_variables_are_protected(self):
        for name in ("Path", "TEMP", "USERPROFILE", "PROGRAMFILES"):
            with self.subTest(name=name):
                self.assertTrue(is_protected_name(name))
                self.assertFalse(is_safe_environment_name(name))

    def test_invalid_names_are_not_safe(self):
        self.assertFalse(is_safe_environment_name("BAD NAME"))
        self.assertFalse(is_safe_environment_name("1LEADING"))
        self.assertFalse(is_safe_environment_name(""))


class RequirementParsingTests(unittest.TestCase):

    def test_pinned_requirement(self):
        requirement = parse_pip_requirement("Django==5.2.4")

        self.assertIsNotNone(requirement)
        self.assertEqual(requirement.name, "Django")
        self.assertEqual(requirement.version, "5.2.4")
        self.assertEqual(requirement.raw, "Django==5.2.4")

    def test_unpinned_requirement_is_rejected(self):
        self.assertIsNone(parse_pip_requirement("Django"))

    def test_options_and_urls_are_rejected(self):
        for line in (
            "-r requirements.txt",
            "--index-url https://example.test",
            "Django @ https://example.test/Django.whl",
            "git+https://example.test/repo.git",
            "Django==5.2.4 --hash=sha256:abc",
            r"C:\local\package.whl",
        ):
            with self.subTest(line=line):
                self.assertIsNone(parse_pip_requirement(line))

    def test_pip_tooling_is_skipped(self):
        self.assertIsNone(parse_pip_requirement("pip==24.0"))
        self.assertIsNone(parse_pip_requirement("setuptools==75.0"))

    def test_freeze_deduplicates_normalized_names(self):
        requirements = parse_pip_freeze(
            [
                "Django==5.2.4",
                "django==5.2.4",
                "git+https://example.test/repo.git",
                "requests==2.32.3 ; python_version >= '3.10'",
            ]
        )

        self.assertEqual(
            [requirement.raw for requirement in requirements],
            ["Django==5.2.4"],
        )

    def test_npm_names(self):
        self.assertTrue(is_valid_npm_name("typescript"))
        self.assertTrue(is_valid_npm_name("@vue/cli"))
        self.assertFalse(is_valid_npm_name("bad name"))
        self.assertFalse(is_valid_npm_name("evil; rm -rf /"))
        self.assertFalse(is_valid_npm_name(""))

    def test_extension_ids(self):
        self.assertTrue(is_valid_extension_id("ms-python.python"))
        self.assertTrue(
            is_valid_extension_id("ms-azuretools.vscode-docker")
        )
        self.assertFalse(is_valid_extension_id("../escape"))
        self.assertFalse(is_valid_extension_id("no-publisher"))
        self.assertFalse(is_valid_extension_id("bad id.ext"))

    def test_wsl_names(self):
        self.assertTrue(is_valid_wsl_name("Ubuntu-22.04"))
        self.assertFalse(is_valid_wsl_name("-d"))
        self.assertFalse(is_valid_wsl_name("Ubuntu; rm -rf /"))

    def test_git_keys(self):
        self.assertTrue(is_valid_git_key("user.name"))
        self.assertTrue(is_valid_git_key("init.defaultBranch"))
        self.assertFalse(is_valid_git_key("alias!"))
        self.assertTrue(is_safe_git_key("user.name"))
        self.assertFalse(is_safe_git_key("credential.helper"))
        self.assertFalse(is_safe_git_key("url.https://example=.insteadOf"))


if __name__ == "__main__":
    unittest.main()
