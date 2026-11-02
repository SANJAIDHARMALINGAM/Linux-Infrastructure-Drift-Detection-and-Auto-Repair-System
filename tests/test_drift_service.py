#!/usr/bin/env python3
"""Comprehensive unit tests for the shared drift service layer."""

import json
import tempfile
import unittest
from pathlib import Path

from core.drift_service import (
    DriftIssue,
    compare_configurations,
    create_backup,
    detect_drift,
    generate_report,
    get_audit_logs,
    get_system_status,
    list_backups,
    list_reports,
    load_json,
    log_event,
    repair_configuration,
    restore_backup,
    save_json_atomic,
    simulate_drift,
    validate_config,
    verify_configuration,
)


class DriftServiceTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp_dir.name)

        self.baseline_file = self.dir / "baseline.json"
        self.current_file = self.dir / "current_config.json"
        self.backup_dir = self.dir / "backups"
        self.reports_dir = self.dir / "reports"
        self.log_file = self.dir / "logs" / "audit.log"

        self.baseline_data = {
            "ssh_root_login": "no",
            "ssh_password_authentication": "no",
            "firewall_enabled": True,
            "auto_updates_enabled": True,
            "file_permissions": "640",
            "backup_enabled": True,
        }

        save_json_atomic(self.baseline_file, self.baseline_data)
        save_json_atomic(self.current_file, self.baseline_data)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_json_atomic_and_load(self):
        test_file = self.dir / "test.json"
        data = {"hello": "world", "num": 42}
        save_json_atomic(test_file, data)

        loaded = load_json(test_file)
        self.assertEqual(loaded, data)

    def test_validate_config(self):
        valid, msg = validate_config(self.baseline_data)
        self.assertTrue(valid)
        self.assertIsNone(msg)

        invalid_type = dict(self.baseline_data)
        invalid_type["firewall_enabled"] = "not_a_bool"
        valid, msg = validate_config(invalid_type)
        self.assertFalse(valid)
        self.assertIn("Invalid type", msg)

        valid, msg = validate_config({})
        self.assertFalse(valid)

    def test_drift_issue_unpacking_and_to_dict(self):
        issue = DriftIssue("firewall_enabled", True, False)
        k, exp, act = issue
        self.assertEqual(k, "firewall_enabled")
        self.assertEqual(exp, True)
        self.assertEqual(act, False)
        self.assertEqual(issue[0], "firewall_enabled")
        self.assertEqual(issue.to_dict(), {
            "key": "firewall_enabled",
            "expected": True,
            "actual": False,
        })

    def test_compare_configurations(self):
        current = dict(self.baseline_data)
        current["ssh_root_login"] = "yes"
        current["extra_key"] = "unexpected"

        drift = compare_configurations(self.baseline_data, current)
        drift_keys = [issue.key for issue in drift]
        self.assertIn("ssh_root_login", drift_keys)
        self.assertIn("extra_key", drift_keys)

    def test_simulate_drift(self):
        res = simulate_drift("3", current_file=self.current_file, log_file=self.log_file)
        self.assertTrue(res["success"])
        self.assertEqual(res["applied_changes"], {"firewall_enabled": False})

        current = load_json(self.current_file)
        self.assertFalse(current["firewall_enabled"])

        with self.assertRaises(ValueError):
            simulate_drift("99", current_file=self.current_file, log_file=self.log_file)

    def test_backup_creation_and_listing(self):
        backup_path = create_backup(
            source_file=self.current_file,
            backup_dir=self.backup_dir,
            log_file=self.log_file,
        )
        self.assertTrue(backup_path.exists())

        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0]["filename"], backup_path.name)
        self.assertIn("size_bytes", backups[0])
        self.assertIn("created_at", backups[0])

    def test_repair_creates_backup_and_verifies(self):
        # Induce drift
        simulate_drift("1", current_file=self.current_file, log_file=self.log_file)
        simulate_drift("5", current_file=self.current_file, log_file=self.log_file)

        initial_drift = detect_drift(self.baseline_file, self.current_file, record_log=False)
        self.assertEqual(len(initial_drift), 2)

        # Execute repair
        result = repair_configuration(
            baseline_file=self.baseline_file,
            current_file=self.current_file,
            backup_dir=self.backup_dir,
            log_file=self.log_file,
            create_backup_first=True,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["repaired"])
        self.assertEqual(result["repaired_count"], 2)
        self.assertIsNotNone(result["backup_path"])
        self.assertTrue(Path(result["backup_path"]).exists())
        self.assertTrue(result["verified"])
        self.assertEqual(result["remaining_drift"], [])

        # Verify current config is restored to baseline
        current = load_json(self.current_file)
        self.assertEqual(current, self.baseline_data)

        # Verify audit log contains repair & backup & verification
        logs = get_audit_logs(self.log_file)
        log_text = " ".join(logs)
        self.assertIn("Automated repair completed", log_text)
        self.assertIn("Repair completed. Backup:", log_text)
        self.assertIn("Post-repair verification passed.", log_text)

    def test_repair_skips_when_compliant(self):
        result = repair_configuration(
            baseline_file=self.baseline_file,
            current_file=self.current_file,
            backup_dir=self.backup_dir,
            log_file=self.log_file,
        )
        self.assertEqual(result["status"], "SKIPPED")
        self.assertFalse(result["repaired"])
        self.assertIsNone(result["backup_path"])

    def test_restore_backup(self):
        # Create initial backup
        b_path = create_backup(self.current_file, self.backup_dir)

        # Modify current
        simulate_drift("3", current_file=self.current_file, log_file=self.log_file)
        self.assertFalse(load_json(self.current_file)["firewall_enabled"])

        # Restore
        res = restore_backup(b_path, target_file=self.current_file, backup_dir=self.backup_dir, log_file=self.log_file)
        self.assertTrue(res["success"])
        self.assertTrue(load_json(self.current_file)["firewall_enabled"])

    def test_generate_and_list_reports(self):
        report_path = generate_report(
            status="COMPLIANT",
            issues=[],
            repairs=[],
            reports_dir=self.reports_dir,
        )
        self.assertTrue(report_path.exists())

        reports = list_reports(self.reports_dir)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["status"], "COMPLIANT")
        self.assertEqual(reports[0]["filename"], report_path.name)

        # Test directory traversal prevention
        with self.assertRaises(ValueError):
            generate_report(filename="../malicious.json", reports_dir=self.reports_dir)

    def test_get_system_status(self):
        status = get_system_status(self.baseline_file, self.current_file)
        self.assertEqual(status["status"], "COMPLIANT")
        self.assertTrue(status["is_compliant"])
        self.assertEqual(status["drift_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
