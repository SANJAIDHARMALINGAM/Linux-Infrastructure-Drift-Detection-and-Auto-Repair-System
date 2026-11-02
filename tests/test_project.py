
import json
import unittest
import tempfile
from pathlib import Path


class ConfigurationTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)

        self.baseline = {
            "ssh_root_login": "no",
            "ssh_password_authentication": "no",
            "firewall_enabled": True,
            "auto_updates_enabled": True,
            "file_permissions": "640",
            "backup_enabled": True
        }

        self.baseline_file = self.directory / "baseline.json"
        self.current_file = self.directory / "current_config.json"

        self.baseline_file.write_text(
            json.dumps(self.baseline), encoding="utf-8"
        )
        self.current_file.write_text(
            json.dumps(self.baseline), encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_baseline_is_valid_json(self):
        data = json.loads(self.baseline_file.read_text(encoding="utf-8"))
        self.assertEqual(data, self.baseline)

    def test_compliant_configuration_has_no_drift(self):
        baseline = json.loads(self.baseline_file.read_text(encoding="utf-8"))
        current = json.loads(self.current_file.read_text(encoding="utf-8"))

        drift = [
            key for key in baseline
            if baseline[key] != current.get(key)
        ]

        self.assertEqual(drift, [])

    def test_single_drift_is_detected(self):
        current = json.loads(self.current_file.read_text(encoding="utf-8"))
        current["ssh_password_authentication"] = "yes"
        self.current_file.write_text(json.dumps(current), encoding="utf-8")

        baseline = json.loads(self.baseline_file.read_text(encoding="utf-8"))
        actual = json.loads(self.current_file.read_text(encoding="utf-8"))

        drift = [
            key for key in baseline
            if baseline[key] != actual.get(key)
        ]

        self.assertEqual(drift, ["ssh_password_authentication"])

    def test_multiple_drift_is_detected(self):
        current = json.loads(self.current_file.read_text(encoding="utf-8"))
        current["ssh_root_login"] = "yes"
        current["firewall_enabled"] = False
        current["backup_enabled"] = False
        self.current_file.write_text(json.dumps(current), encoding="utf-8")

        baseline = json.loads(self.baseline_file.read_text(encoding="utf-8"))
        actual = json.loads(self.current_file.read_text(encoding="utf-8"))

        drift = [
            key for key in baseline
            if baseline[key] != actual.get(key)
        ]

        self.assertEqual(len(drift), 3)

    def test_invalid_json_is_rejected(self):
        self.current_file.write_text("{invalid json", encoding="utf-8")

        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.current_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
