#!/usr/bin/env python3
"""Linux Infrastructure Auto Repair utility.

Provides automated remediation of drifted settings back to baseline values
with mandatory pre-repair backups and verification.
"""

from pathlib import Path

from core.drift_service import (
    BACKUP_DIR,
    BASELINE_FILE,
    CURRENT_FILE,
    LOG_FILE,
    load_json,
    log_event,
    repair_configuration as service_repair_configuration,
    save_json,
)

BASE_DIR = Path(__file__).resolve().parent


def log(message: str) -> None:
    """Log an event message to audit log."""
    log_event(message, log_file=LOG_FILE)


def repair_configuration() -> None:
    """Prompt user and perform safe configuration repair with backup and verification."""
    if not BASELINE_FILE.exists() or not CURRENT_FILE.exists():
        print("ERROR: Required JSON configuration file is missing.")
        return

    try:
        baseline = load_json(BASELINE_FILE)
        current = load_json(CURRENT_FILE)
    except (ValueError, OSError) as error:
        print(f"ERROR: Cannot read configuration: {error}")
        log(f"Repair failed: {error}")
        return

    drift = {
        key: (current.get(key), expected)
        for key, expected in baseline.items()
        if current.get(key) != expected
    }

    if not drift:
        print("No configuration drift detected.")
        log("Repair skipped: no drift detected.")
        return

    print("\nDetected configuration drift:")
    for key, (actual, expected) in drift.items():
        print(f"{key}: {actual!r} -> {expected!r}")

    confirm = input("\nApply repairs? (y/n): ").strip().lower()
    if confirm != "y":
        print("Repair cancelled.")
        log("Repair cancelled by user.")
        return

    try:
        result = service_repair_configuration(
            baseline_file=BASELINE_FILE,
            current_file=CURRENT_FILE,
            backup_dir=BACKUP_DIR,
            log_file=LOG_FILE,
            create_backup_first=True,
        )

        if not result["verified"]:
            print("WARNING: Verification failed.")
            print("Remaining drift:", ", ".join([d["key"] for d in result["remaining_drift"]]))
            return

        print("\nRepair completed successfully.")
        if result.get("backup_path"):
            print(f"Backup saved: {result['backup_path']}")
        print("Verification: PASSED")

    except (OSError, ValueError) as error:
        print(f"ERROR during repair: {error}")
        log(f"Repair failed: {error}")


if __name__ == "__main__":
    repair_configuration()
