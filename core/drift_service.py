#!/usr/bin/env python3
"""Shared core service layer for Linux Infrastructure Drift Detection & Auto Repair System.

This module provides common business logic consumed by both the CLI interface
and the Flask web dashboard, including:
- Baseline and current configuration management with atomic writes
- Schema and type validation
- Drift detection and discrepancy analysis
- Drift simulation
- Timestamped backup creation, listing, and restoration
- Safe configuration repair with mandatory pre-repair backups and post-repair verification
- Structured JSON report generation and retrieval
- Centralized audit logging
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Default directory locations relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent
BASELINE_FILE = BASE_DIR / "baseline.json"
CURRENT_FILE = BASE_DIR / "current_config.json"
BACKUP_DIR = BASE_DIR / "backups"
REPORTS_DIR = BASE_DIR / "reports"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "audit.log"

# Standard simulation presets
SIMULATION_PRESETS: Dict[str, Dict[str, Any]] = {
    "1": {
        "label": "Enable SSH root login",
        "changes": {"ssh_root_login": "yes"}
    },
    "2": {
        "label": "Enable SSH password authentication",
        "changes": {"ssh_password_authentication": "yes"}
    },
    "3": {
        "label": "Disable firewall",
        "changes": {"firewall_enabled": False}
    },
    "4": {
        "label": "Disable automatic updates",
        "changes": {"auto_updates_enabled": False}
    },
    "5": {
        "label": "Change file permissions",
        "changes": {"file_permissions": "777"}
    },
    "6": {
        "label": "Disable backups",
        "changes": {"backup_enabled": False}
    },
    "7": {
        "label": "Apply all test changes",
        "changes": {
            "ssh_root_login": "yes",
            "ssh_password_authentication": "yes",
            "firewall_enabled": False,
            "auto_updates_enabled": False,
            "file_permissions": "777",
            "backup_enabled": False,
        }
    }
}


class DriftIssue:
    """Represents an individual configuration drift item.
    
    Supports both tuple-unpacking (key, expected, actual) for CLI backward
    compatibility and dictionary conversion for JSON/API responses.
    """

    def __init__(self, key: str, expected: Any, actual: Any):
        self.key = key
        self.expected = expected
        self.actual = actual

    def __iter__(self):
        return iter((self.key, self.expected, self.actual))

    def __getitem__(self, index: int):
        return (self.key, self.expected, self.actual)[index]

    def __len__(self):
        return 3

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, (tuple, list)) and len(other) == 3:
            return (self.key, self.expected, self.actual) == tuple(other)
        if isinstance(other, DriftIssue):
            return (self.key, self.expected, self.actual) == (other.key, other.expected, other.actual)
        return False

    def __repr__(self) -> str:
        return f"DriftIssue(key={self.key!r}, expected={self.expected!r}, actual={self.actual!r})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "expected": self.expected,
            "actual": self.actual,
        }


# ============================================================================
# File I/O & Safe Writing
# ============================================================================

def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON from a file with error handling."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path.name}")
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            if not isinstance(data, dict):
                raise ValueError(f"Configuration file {path.name} must contain a JSON object.")
            return data
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path.name}: {error}") from error
    except OSError as error:
        raise OSError(f"Unable to read {path.name}: {error}") from error


def save_json_atomic(path: Path, data: Any) -> None:
    """Save data to a JSON file atomically using a temporary file.
    
    Guarantees that files are never left in a corrupted or partially-written state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = None
    try:
        # Create temporary file in the same directory to allow atomic os.replace across filesystem boundaries
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tf:
            temp_file = Path(tf.name)
            json.dump(data, tf, indent=4)
            tf.write("\n")
            tf.flush()
            os.fsync(tf.fileno())

        os.replace(temp_file, path)
        temp_file = None
    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def save_json(path: Path, data: Any) -> None:
    """Compatibility wrapper for saving JSON files atomically."""
    save_json_atomic(path, data)


# ============================================================================
# Audit Logging
# ============================================================================

def log_event(message: str, log_file: Path = LOG_FILE) -> None:
    """Append a timestamped message to the audit log."""
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_file.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
    except OSError as error:
        # Non-fatal error for logging
        print(f"WARNING: Unable to write to audit log: {error}")


def get_audit_logs(log_file: Path = LOG_FILE, limit: Optional[int] = None) -> List[str]:
    """Retrieve audit log lines, newest first or full list."""
    if not log_file.exists() or log_file.stat().st_size == 0:
        return []
    try:
        with log_file.open("r", encoding="utf-8") as file:
            lines = [line.rstrip("\r\n") for line in file if line.strip()]
            if limit:
                return lines[-limit:]
            return lines
    except OSError:
        return []


# ============================================================================
# Configuration Management & Validation
# ============================================================================

def initialize_system(
    baseline_file: Path = BASELINE_FILE,
    current_file: Path = CURRENT_FILE,
    log_file: Path = LOG_FILE,
    backup_dir: Path = BACKUP_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> None:
    """Initialize system directories and default configuration files."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not log_file.exists():
        log_file.touch(exist_ok=True)

    if not baseline_file.exists():
        raise FileNotFoundError(f"Baseline configuration missing: {baseline_file.name}")

    if not current_file.exists():
        baseline_data = load_json(baseline_file)
        save_json_atomic(current_file, baseline_data)

    log_event("System initialized.", log_file=log_file)


def load_baseline(baseline_file: Path = BASELINE_FILE) -> Dict[str, Any]:
    """Load baseline configuration."""
    return load_json(baseline_file)


def load_current_config(current_file: Path = CURRENT_FILE) -> Dict[str, Any]:
    """Load current test configuration."""
    return load_json(current_file)


def validate_config(config_data: Any) -> Tuple[bool, Optional[str]]:
    """Validate that configuration data has expected structure and types."""
    if not isinstance(config_data, dict):
        return False, "Configuration must be a JSON object."
    if not config_data:
        return False, "Configuration dictionary cannot be empty."

    # Validate standard key value types if present
    type_expectations = {
        "ssh_root_login": str,
        "ssh_password_authentication": str,
        "firewall_enabled": bool,
        "auto_updates_enabled": bool,
        "file_permissions": str,
        "backup_enabled": bool,
    }

    for key, expected_type in type_expectations.items():
        if key in config_data and not isinstance(config_data[key], expected_type):
            return False, f"Invalid type for '{key}': expected {expected_type.__name__}, got {type(config_data[key]).__name__}"

    return True, None


# ============================================================================
# Drift Detection & Comparison
# ============================================================================

def compare_configurations(
    baseline: Dict[str, Any], current: Dict[str, Any]
) -> List[DriftIssue]:
    """Compare baseline and current configuration dictionaries and return drift issues."""
    drift: List[DriftIssue] = []
    all_keys = sorted(set(baseline.keys()) | set(current.keys()))

    for key in all_keys:
        expected = baseline.get(key, "<MISSING>")
        actual = current.get(key, "<MISSING>")
        if expected != actual:
            drift.append(DriftIssue(key, expected, actual))

    return drift


def detect_drift(
    baseline_file: Path = BASELINE_FILE,
    current_file: Path = CURRENT_FILE,
    log_file: Path = LOG_FILE,
    record_log: bool = True,
) -> List[DriftIssue]:
    """Detect configuration drift between baseline and current configuration files."""
    baseline = load_json(baseline_file)
    current = load_json(current_file)
    drift = compare_configurations(baseline, current)

    if record_log:
        log_event(f"Drift scan completed: {len(drift)} issue(s) found.", log_file=log_file)

    return drift


def get_system_status(
    baseline_file: Path = BASELINE_FILE,
    current_file: Path = CURRENT_FILE,
) -> Dict[str, Any]:
    """Get high-level status summary for both CLI and API."""
    baseline = load_json(baseline_file)
    current = load_json(current_file)
    drift = compare_configurations(baseline, current)
    status_str = "NON-COMPLIANT" if drift else "COMPLIANT"

    return {
        "status": status_str,
        "total_baseline_settings": len(baseline),
        "total_current_settings": len(current),
        "drift_count": len(drift),
        "is_compliant": len(drift) == 0,
        "drift": [issue.to_dict() for issue in drift],
        "current_config": current,
        "baseline_config": baseline,
    }


# ============================================================================
# Drift Simulation
# ============================================================================

def simulate_drift(
    option: str,
    current_file: Path = CURRENT_FILE,
    log_file: Path = LOG_FILE,
) -> Dict[str, Any]:
    """Simulate configuration drift by updating test configuration JSON file."""
    if option not in SIMULATION_PRESETS:
        raise ValueError(f"Invalid simulation option '{option}'. Choose from 1-7.")

    current = load_json(current_file)
    preset = SIMULATION_PRESETS[option]
    current.update(preset["changes"])

    save_json_atomic(current_file, current)
    log_event(f"Simulated drift using option {option}.", log_file=log_file)

    return {
        "success": True,
        "option": option,
        "label": preset["label"],
        "applied_changes": preset["changes"],
        "updated_config": current,
    }


# ============================================================================
# Backups Management
# ============================================================================

def create_backup(
    source_file: Path = CURRENT_FILE,
    backup_dir: Path = BACKUP_DIR,
    log_file: Path = LOG_FILE,
    record_log: bool = False,
) -> Path:
    """Create a timestamped backup copy of a configuration file before changes."""
    if not source_file.exists():
        raise FileNotFoundError(f"Cannot backup non-existent file: {source_file.name}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"current_config_{timestamp}.json"

    # Avoid duplicate name collision within same second
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / f"current_config_{timestamp}_{counter}.json"
        counter += 1

    shutil.copy2(source_file, backup_path)

    if record_log:
        log_event(f"Backup created: {backup_path.name}", log_file=log_file)

    return backup_path


def list_backups(backup_dir: Path = BACKUP_DIR) -> List[Dict[str, Any]]:
    """List all available configuration backups sorted newest first."""
    if not backup_dir.exists():
        return []

    backups = []
    for item in backup_dir.glob("*.json"):
        if item.is_file():
            stat = item.stat()
            created_dt = datetime.fromtimestamp(stat.st_mtime)
            backups.append({
                "filename": item.name,
                "path": str(item.resolve()),
                "size_bytes": stat.st_size,
                "created_at": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_epoch": stat.st_mtime,
            })

    backups.sort(key=lambda b: b["timestamp_epoch"], reverse=True)
    return backups


def restore_backup(
    backup_filename_or_path: Union[str, Path],
    target_file: Path = CURRENT_FILE,
    backup_dir: Path = BACKUP_DIR,
    log_file: Path = LOG_FILE,
) -> Dict[str, Any]:
    """Restore configuration from an existing backup file."""
    if isinstance(backup_filename_or_path, str):
        backup_path = backup_dir / backup_filename_or_path
        if not backup_path.exists():
            backup_path = Path(backup_filename_or_path)
    else:
        backup_path = backup_filename_or_path

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path.name}")

    # Validate JSON before restoring
    backup_data = load_json(backup_path)
    is_valid, error = validate_config(backup_data)
    if not is_valid:
        raise ValueError(f"Backup file is corrupted or invalid: {error}")

    # Create safety backup of current state before restoring
    create_backup(target_file, backup_dir)

    save_json_atomic(target_file, backup_data)
    log_event(f"Restored configuration from backup: {backup_path.name}", log_file=log_file)

    return {
        "success": True,
        "restored_from": backup_path.name,
        "restored_config": backup_data,
    }


# ============================================================================
# Auto Repair & Verification
# ============================================================================

def verify_configuration(
    baseline_file: Path = BASELINE_FILE,
    current_file: Path = CURRENT_FILE,
) -> Tuple[bool, List[DriftIssue]]:
    """Verify that current configuration is compliant with baseline."""
    drift = detect_drift(baseline_file, current_file, record_log=False)
    return len(drift) == 0, drift


def repair_configuration(
    baseline_file: Path = BASELINE_FILE,
    current_file: Path = CURRENT_FILE,
    backup_dir: Path = BACKUP_DIR,
    log_file: Path = LOG_FILE,
    create_backup_first: bool = True,
) -> Dict[str, Any]:
    """Perform automated configuration repair.
    
    1. Detects drift.
    2. If drift found, creates a timestamped backup before touching current config.
    3. Restores compliant baseline settings safely.
    4. Runs post-repair verification check.
    5. Appends all actions and verification results to audit log.
    """
    baseline = load_json(baseline_file)
    current = load_json(current_file)
    drift = compare_configurations(baseline, current)

    if not drift:
        log_event("Repair skipped: no drift detected.", log_file=log_file)
        return {
            "success": True,
            "status": "SKIPPED",
            "message": "No configuration drift detected. System is compliant.",
            "repaired": False,
            "repaired_count": 0,
            "backup_path": None,
            "verified": True,
            "remaining_drift": [],
        }

    backup_path = None
    if create_backup_first:
        backup_path = create_backup(current_file, backup_dir, log_file=log_file)

    # Apply baseline values for drifted settings
    repaired_config = current.copy()
    for issue in drift:
        if issue.expected == "<MISSING>":
            repaired_config.pop(issue.key, None)
        else:
            repaired_config[issue.key] = issue.expected

    # If baseline had keys that were missing in current, ensure they are added
    for key, value in baseline.items():
        repaired_config[key] = value

    save_json_atomic(current_file, repaired_config)

    log_event(f"Automated repair completed for {len(drift)} issue(s).", log_file=log_file)
    if backup_path:
        log_event(f"Repair completed. Backup: {backup_path}", log_file=log_file)

    # Post-repair verification
    verified, remaining = verify_configuration(baseline_file, current_file)

    if verified:
        log_event("Post-repair verification passed.", log_file=log_file)
    else:
        log_event(f"Post-repair verification failed: {len(remaining)} issue(s) remain.", log_file=log_file)

    return {
        "success": True,
        "status": "REPAIRED",
        "message": "Repair completed successfully.",
        "repaired": True,
        "repaired_count": len(drift),
        "backup_path": str(backup_path) if backup_path else None,
        "backup_filename": backup_path.name if backup_path else None,
        "verified": verified,
        "remaining_drift": [issue.to_dict() for issue in remaining],
        "repaired_issues": [issue.to_dict() for issue in drift],
    }


# ============================================================================
# Report Generation & Listing
# ============================================================================

def generate_report(
    status: str = "COMPLIANT",
    issues: Optional[List[Any]] = None,
    repairs: Optional[List[Any]] = None,
    filename: Optional[str] = None,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Generate a timestamped JSON drift detection report."""
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "issues": issues or [],
        "repairs": repairs or [],
    }

    if filename is None:
        filename = (
            "drift_report_"
            + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            + ".json"
        )

    report_path = reports_dir / filename

    # Prevent directory traversal attacks
    if report_path.parent.resolve() != reports_dir.resolve():
        raise ValueError("Invalid report filename: Path traversal is not permitted.")

    save_json_atomic(report_path, report_data)
    return report_path


def list_reports(reports_dir: Path = REPORTS_DIR) -> List[Dict[str, Any]]:
    """List historical reports sorted newest first with metadata."""
    if not reports_dir.exists():
        return []

    reports = []
    for item in reports_dir.glob("*.json"):
        if item.is_file():
            try:
                data = load_json(item)
                stat = item.stat()
                reports.append({
                    "filename": item.name,
                    "path": str(item.resolve()),
                    "timestamp": data.get("timestamp"),
                    "status": data.get("status", "UNKNOWN"),
                    "issue_count": len(data.get("issues", [])),
                    "repair_count": len(data.get("repairs", [])),
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "mtime": stat.st_mtime,
                })
            except Exception:
                continue

    reports.sort(key=lambda r: r["mtime"], reverse=True)
    return reports
