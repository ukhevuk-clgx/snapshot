import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import config


class ConfigTests(unittest.TestCase):
    def test_local_credentials_and_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            path.write_text(json.dumps({
                "SITE": " https://example.atlassian.net/ ",
                "EMAIL": "local@example.com", "TOKEN": "test-only-placeholder",
            }), encoding="utf-8")
            values = config.load_credentials(path, {"JIRA_EMAIL": " env@example.com "})
            self.assertEqual(values["SITE"], "https://example.atlassian.net/")
            self.assertEqual(values["EMAIL"], "env@example.com")
            self.assertEqual(values["TOKEN"], "test-only-placeholder")

    def test_missing_credentials_do_not_prevent_offline_import(self):
        with tempfile.TemporaryDirectory() as directory:
            values = config.load_credentials(Path(directory) / "missing.json", {})
            self.assertEqual(values, {"SITE": "", "EMAIL": "", "TOKEN": ""})

    def test_complete_environment_does_not_read_local_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            path.write_text("invalid", encoding="utf-8")
            env = {"JIRA_SITE": "https://example.atlassian.net", "JIRA_EMAIL": "a@example.com",
                   "JIRA_TOKEN": "test-only-placeholder"}
            self.assertEqual(config.load_credentials(path, env)["SITE"], env["JIRA_SITE"])

    def test_explicit_empty_environment_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            path.write_text('{"TOKEN": "test-only-placeholder"}', encoding="utf-8")
            self.assertEqual(config.load_credentials(path, {"JIRA_TOKEN": ""})["TOKEN"], "")

    def test_invalid_file_error_does_not_include_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            path.write_text('{"TOKEN": sensitive-invalid-value}', encoding="utf-8")
            with self.assertRaises(ValueError) as error:
                config.load_credentials(path, {})
            self.assertNotIn("sensitive-invalid-value", str(error.exception))

    def test_invalid_structure_and_types_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            for value in ([], {"TOKEN": 123}):
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    config.load_credentials(path, {})

    def test_missing_token_and_insecure_site_are_rejected(self):
        with patch.multiple(config, SITE="https://example.atlassian.net", EMAIL="test@example.com", TOKEN=""):
            with self.assertRaisesRegex(ValueError, "TOKEN is empty"):
                config.validate_config()
        with patch.multiple(config, SITE="http://example.atlassian.net", EMAIL="test@example.com",
                            TOKEN="test-only-placeholder"):
            with self.assertRaisesRegex(ValueError, "https://"):
                config.validate_config()


if __name__ == "__main__":
    unittest.main()
