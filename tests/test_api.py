#!/usr/bin/env python3
"""Comprehensive test suite for Flask REST API."""

import json
import tempfile
import unittest
from pathlib import Path

from app import create_app
from core.drift_service import save_json_atomic


class FlaskAPITests(unittest.TestCase):

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

        self.app = create_app({
            "TESTING": True,
            "BASELINE_FILE": self.baseline_file,
            "CURRENT_FILE": self.current_file,
            "BACKUP_DIR": self.backup_dir,
            "REPORTS_DIR": self.reports_dir,
            "LOG_FILE": self.log_file,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)

    def test_serve_dashboard_ui(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"DriftGuard", response.data)
        self.assertIn(b"Linux Infrastructure", response.data)

    def test_dashboard_data(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["system_status"], "COMPLIANT")
        self.assertTrue(data["is_compliant"])
        self.assertEqual(data["drift_count"], 0)
        self.assertEqual(data["total_baseline_settings"], 6)

    def test_configuration_retrieval(self):
        response = self.client.get("/api/configuration")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["baseline"], self.baseline_data)
        self.assertEqual(data["current"], self.baseline_data)
        self.assertEqual(len(data["settings"]), 6)

    def test_drift_detection_compliant(self):
        response = self.client.get("/api/drift")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["drift_count"], 0)
        self.assertTrue(data["is_compliant"])

    def test_trigger_drift_detect_generates_report(self):
        response = self.client.post("/api/drift/detect")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("report_generated", data)
        self.assertTrue((self.reports_dir / data["report_generated"]).exists())

    def test_simulate_drift_preset(self):
        response = self.client.post("/api/drift/simulate", json={"option": "1"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")

        # Verify drift is now reported
        drift_resp = self.client.get("/api/drift")
        drift_data = drift_resp.get_json()
        self.assertEqual(drift_data["drift_count"], 1)
        self.assertEqual(drift_data["drift"][0]["key"], "ssh_root_login")
        self.assertEqual(drift_data["drift"][0]["actual"], "yes")

    def test_simulate_drift_custom_valid(self):
        response = self.client.post("/api/drift/simulate", json={
            "changes": {"firewall_enabled": False, "file_permissions": "777"}
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")

        drift_resp = self.client.get("/api/drift")
        drift_data = drift_resp.get_json()
        self.assertEqual(drift_data["drift_count"], 2)

    def test_simulate_drift_invalid_requests(self):
        # Non-json or missing body
        res = self.client.post("/api/drift/simulate", data="not json")
        self.assertEqual(res.status_code, 400)

        # Invalid option number
        res = self.client.post("/api/drift/simulate", json={"option": "99"})
        self.assertEqual(res.status_code, 400)

        # Disallowed key (security test)
        res = self.client.post("/api/drift/simulate", json={
            "changes": {"malicious_command": "rm -rf /"}
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Disallowed configuration key", res.get_json()["error"])

    def test_repair_requires_confirmation(self):
        # Induce drift first
        self.client.post("/api/drift/simulate", json={"option": "2"})

        # Try repairing without confirmation
        res = self.client.post("/api/repair", json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirmation required", res.get_json()["error"])

        res = self.client.post("/api/repair", json={"confirm": False})
        self.assertEqual(res.status_code, 400)

    def test_repair_with_backup_and_verification(self):
        # Induce drift
        self.client.post("/api/drift/simulate", json={"option": "3"})

        # Confirm repair
        response = self.client.post("/api/repair", json={"confirm": True})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        repair_res = data["repair_result"]
        self.assertTrue(repair_res["repaired"])
        self.assertTrue(repair_res["verified"])
        self.assertIsNotNone(repair_res["backup_path"])
        self.assertTrue(Path(repair_res["backup_path"]).exists())
        self.assertIn("report_generated", repair_res)

        # Verify drift is back to 0
        drift_resp = self.client.get("/api/drift")
        self.assertEqual(drift_resp.get_json()["drift_count"], 0)

    def test_audit_logs_retrieval(self):
        # Trigger an action to create log
        self.client.post("/api/drift/simulate", json={"option": "4"})
        response = self.client.get("/api/logs?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertGreater(data["count"], 0)
        self.assertTrue(any("Simulated drift" in line for line in data["logs"]))

    def test_backups_listing_and_restore(self):
        # Induce drift and repair to generate a backup
        self.client.post("/api/drift/simulate", json={"option": "5"})
        repair_res = self.client.post("/api/repair", json={"confirm": True}).get_json()
        backup_filename = repair_res["repair_result"]["backup_filename"]

        # List backups
        list_resp = self.client.get("/api/backups")
        self.assertEqual(list_resp.status_code, 200)
        backups = list_resp.get_json()["backups"]
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]["filename"], backup_filename)

        # Restore without confirm should fail
        res = self.client.post("/api/backups/restore", json={"filename": backup_filename})
        self.assertEqual(res.status_code, 400)

        # Restore with path traversal should fail
        res = self.client.post("/api/backups/restore", json={"confirm": True, "filename": "../malicious.json"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Path traversal", res.get_json()["error"])

        # Valid restore
        res = self.client.post("/api/backups/restore", json={"confirm": True, "filename": backup_filename})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "success")

    def test_reports_listing_and_retrieval(self):
        # Trigger scan to generate report
        detect_resp = self.client.post("/api/drift/detect").get_json()
        report_filename = detect_resp["report_generated"]

        # List reports
        list_resp = self.client.get("/api/reports")
        self.assertEqual(list_resp.status_code, 200)
        reports = list_resp.get_json()["reports"]
        self.assertGreaterEqual(len(reports), 1)

        # Get specific report
        get_rep = self.client.get(f"/api/reports/{report_filename}")
        self.assertEqual(get_rep.status_code, 200)
        self.assertEqual(get_rep.get_json()["report"]["status"], "COMPLIANT")

        # Path traversal test on reports
        bad_rep = self.client.get("/api/reports/..%2F..%2Fetc%2Fpasswd")
        self.assertIn(bad_rep.status_code, [404, 400])


if __name__ == "__main__":
    unittest.main(verbosity=2)
