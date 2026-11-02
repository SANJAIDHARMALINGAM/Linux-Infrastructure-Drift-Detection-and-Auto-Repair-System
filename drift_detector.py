#!/usr/bin/env python3
"""Linux Infrastructure Drift Detection & Auto Repair System CLI.

Interactive command-line interface for viewing configuration status,
detecting drift, simulating drift, auto-repairing configuration,
and inspecting audit logs.
"""

import json
from pathlib import Path
from typing import List

from core.drift_service import (
    BACKUP_DIR,
    BASELINE_FILE,
    CURRENT_FILE,
    LOG_FILE,
    SIMULATION_PRESETS,
    DriftIssue,
    detect_drift as service_detect_drift,
    get_audit_logs,
    get_system_status,
    initialize_system,
    load_json,
    log_event as service_log_event,
    repair_configuration as service_repair_configuration,
    save_json,
    simulate_drift as service_simulate_drift,
)

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"


def log_event(message: str) -> None:
    """Log an audit event message."""
    service_log_event(message, log_file=LOG_FILE)


def initialize() -> None:
    """Initialize system configuration and directories."""
    initialize_system(
        baseline_file=BASELINE_FILE,
        current_file=CURRENT_FILE,
        log_file=LOG_FILE,
        backup_dir=BACKUP_DIR,
    )


def print_header() -> None:
    """Print standard application header banner."""
    print("\n" + "=" * 66)
    print(" LINUX INFRASTRUCTURE DRIFT DETECTION & AUTO REPAIR SYSTEM")
    print("=" * 66)


def detect_drift(show: bool = True) -> List[DriftIssue]:
    """Detect differences between baseline and current configuration."""
    drift = service_detect_drift(
        baseline_file=BASELINE_FILE,
        current_file=CURRENT_FILE,
        log_file=LOG_FILE,
        record_log=True,
    )

    if show:
        print("\n[DRIFT DETECTION REPORT]")
        print("-" * 66)

        if not drift:
            print("STATUS: COMPLIANT")
            print("No configuration drift detected.")
        else:
            print(f"STATUS: DRIFT DETECTED ({len(drift)} issue(s))")
            for key, expected, actual in drift:
                print(f"\nSetting : {key}")
                print(f"Expected: {expected}")
                print(f"Actual  : {actual}")

        print("-" * 66)

    return drift


def show_status() -> None:
    """Display current configuration values and compliance summary."""
    status_info = get_system_status(BASELINE_FILE, CURRENT_FILE)
    current = status_info["current_config"]
    drift = status_info["drift"]

    print("\n[CURRENT CONFIGURATION]")
    print("-" * 66)

    for key, value in sorted(current.items()):
        print(f"{key:<36} : {value}")

    print("-" * 66)
    print(f"Total settings in baseline : {status_info['total_baseline_settings']}")
    print(f"Settings with drift        : {status_info['drift_count']}")
    print(f"Compliance status          : {status_info['status']}")


def simulate_drift() -> None:
    """Display drift simulation menu and apply selected scenario."""
    print("\n[SIMULATE CONFIGURATION DRIFT]")
    for opt, preset in sorted(SIMULATION_PRESETS.items()):
        print(f"{opt}. {preset['label']}")
    print("0. Cancel")

    choice = input("\nChoose an option: ").strip()

    if choice == "0":
        print("Simulation cancelled.")
        return

    if choice not in SIMULATION_PRESETS:
        print("Invalid choice.")
        return

    try:
        service_simulate_drift(choice, current_file=CURRENT_FILE, log_file=LOG_FILE)
        print("\nTest drift successfully introduced.")
        print("No real system configuration was modified.")
    except Exception as error:
        print(f"ERROR introducing drift: {error}")


def repair_drift() -> None:
    """Prompt user and execute automated repair with pre-backup and verification."""
    drift = service_detect_drift(
        baseline_file=BASELINE_FILE,
        current_file=CURRENT_FILE,
        log_file=LOG_FILE,
        record_log=False,
    )

    print("\n[AUTOMATED CONFIGURATION REPAIR]")

    if not drift:
        print("No repair required. System is compliant.")
        log_event("Repair requested: no drift found.")
        return

    print(f"Detected issues: {len(drift)}")

    for key, expected, actual in drift:
        print(f"Repairing {key}: {actual} -> {expected}")

    confirm = input(
        "\nApply repairs to project test configuration? (y/n): "
    ).strip().lower()

    if confirm != "y":
        print("Repair cancelled.")
        log_event("Repair cancelled by user.")
        return

    result = service_repair_configuration(
        baseline_file=BASELINE_FILE,
        current_file=CURRENT_FILE,
        backup_dir=BACKUP_DIR,
        log_file=LOG_FILE,
        create_backup_first=True,
    )

    if result.get("backup_path"):
        print(f"Backup created before repair: {result['backup_path']}")

    print("\nRepair completed successfully.")

    if result["verified"]:
        print("Verification: PASSED")
        print("System status: COMPLIANT")
    else:
        print("Verification: FAILED")
        print("System status: NON-COMPLIANT")


def show_logs() -> None:
    """Display recorded audit logs."""
    print("\n[AUDIT LOG]")
    print("-" * 66)

    lines = get_audit_logs(LOG_FILE)
    if not lines:
        print("No audit events recorded yet.")
        return

    print("\n".join(lines))


def main() -> None:
    """CLI main loop."""
    initialize()

    while True:
        print_header()
        print("1. View current configuration")
        print("2. Detect configuration drift")
        print("3. Simulate configuration drift")
        print("4. Automatically repair drift")
        print("5. View audit logs")
        print("6. Exit")

        choice = input("\nEnter your choice (1-6): ").strip()

        if choice == "1":
            show_status()
        elif choice == "2":
            detect_drift()
        elif choice == "3":
            simulate_drift()
        elif choice == "4":
            repair_drift()
        elif choice == "5":
            show_logs()
        elif choice == "6":
            print("\nExiting Linux Drift Detection System.")
            break
        else:
            print("Invalid choice. Please select 1-6.")

        input("\nPress Enter to return to the main menu...")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"\nERROR: {error}")
        raise SystemExit(1)
