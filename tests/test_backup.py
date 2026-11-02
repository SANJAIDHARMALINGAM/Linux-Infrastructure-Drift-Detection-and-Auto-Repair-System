
import json
import tempfile
import unittest
import shutil
from pathlib import Path


class BackupTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.config_file = self.root / "current_config.json"
        self.backup_dir = self.root / "backups"
        self.backup_dir.mkdir()

        self.original_config = {
            "ssh_root_login": "no",
            "ssh_password_authentication": "no",
            "firewall_enabled": True,
            "auto_updates_enabled": True,
            "file_permissions": "640",
            "backup_enabled": True
        }

        self.config_file.write_text(
            json.dumps(self.original_config, indent=2),
            encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_backup_preserves_configuration(self):
        backup_file = self.backup_dir / "current_config.json.backup"
        shutil.copy2(self.config_file, backup_file)

        original = json.loads(
            self.config_file.read_text(encoding="utf-8")
        )
        backup = json.loads(
            backup_file.read_text(encoding="utf-8")
        )

        self.assertEqual(original, backup)

    def test_backup_can_restore_configuration(self):
        backup_file = self.backup_dir / "current_config.json.backup"
        shutil.copy2(self.config_file, backup_file)

        changed_config = dict(self.original_config)
        changed_config["ssh_password_authentication"] = "yes"

        self.config_file.write_text(
            json.dumps(changed_config),
            encoding="utf-8"
        )

        shutil.copy2(backup_file, self.config_file)

        restored = json.loads(
            self.config_file.read_text(encoding="utf-8")
        )

        self.assertEqual(restored, self.original_config)


if __name__ == "__main__":
    unittest.main(verbosity=2)

