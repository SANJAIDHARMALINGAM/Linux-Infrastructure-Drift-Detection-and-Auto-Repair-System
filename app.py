#!/usr/bin/env python3
"""Flask REST API for Linux Infrastructure Drift Detection & Auto Repair System.

Exposes RESTful endpoints for configuration inspection, drift detection,
simulation, automated remediation with pre-repair backups, post-repair
verification, report management, and audit trail inspection.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from core.drift_service import (
    BACKUP_DIR,
    BASELINE_FILE,
    CURRENT_FILE,
    LOG_FILE,
    REPORTS_DIR,
    SIMULATION_PRESETS,
    create_backup,
    detect_drift,
    generate_report,
    get_audit_logs,
    get_system_status,
    initialize_system,
    list_backups,
    list_reports,
    load_baseline,
    load_current_config,
    load_json,
    log_event,
    repair_configuration,
    restore_backup,
    save_json_atomic,
    simulate_drift,
    validate_config,
    verify_configuration,
)

# Allowed configuration keys for safe validation
ALLOWED_CONFIG_KEYS = {
    "ssh_root_login",
    "ssh_password_authentication",
    "firewall_enabled",
    "auto_updates_enabled",
    "file_permissions",
    "backup_enabled",
}

# Global lock to synchronize configuration write operations and avoid concurrent file corruption
CONFIG_WRITE_LOCK = threading.Lock()


def create_app(config: Dict[str, Any] = None) -> Flask:
    """Application factory for Flask REST API."""
    app = Flask(__name__)

    # Default paths (can be overridden in config for testing)
    app.config["BASELINE_FILE"] = BASELINE_FILE
    app.config["CURRENT_FILE"] = CURRENT_FILE
    app.config["BACKUP_DIR"] = BACKUP_DIR
    app.config["REPORTS_DIR"] = REPORTS_DIR
    app.config["LOG_FILE"] = LOG_FILE

    if config:
        app.config.update(config)

    # Initialize environment directories
    try:
        initialize_system(
            baseline_file=app.config["BASELINE_FILE"],
            current_file=app.config["CURRENT_FILE"],
            log_file=app.config["LOG_FILE"],
            backup_dir=app.config["BACKUP_DIR"],
            reports_dir=app.config["REPORTS_DIR"],
        )
    except Exception as error:
        app.logger.warning(f"Initialization warning: {error}")

    # ------------------------------------------------------------------------
    # Error Handlers
    # ------------------------------------------------------------------------

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return jsonify({
            "status": "error",
            "code": e.code,
            "error": e.description,
        }), e.code

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
        return jsonify({
            "status": "error",
            "code": 500,
            "error": "Internal server error",
            "details": str(e),
        }), 500

    # ------------------------------------------------------------------------
    # Web UI Routes
    # ------------------------------------------------------------------------

    @app.route("/", methods=["GET"])
    @app.route("/overview", methods=["GET"])
    @app.route("/configuration", methods=["GET"])
    @app.route("/drift", methods=["GET"])
    @app.route("/repair", methods=["GET"])
    @app.route("/backups", methods=["GET"])
    @app.route("/reports", methods=["GET"])
    @app.route("/logs", methods=["GET"])
    @app.route("/about", methods=["GET"])
    def serve_dashboard():
        """Serve the graphical web dashboard."""
        return render_template("index.html")

    # ------------------------------------------------------------------------
    # API Routes
    # ------------------------------------------------------------------------

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """1. Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "Linux Infrastructure Drift Detection & Auto Repair API",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200

    @app.route("/api/dashboard", methods=["GET"])
    def get_dashboard():
        """2. Dashboard summary statistics and system state."""
        try:
            status_data = get_system_status(
                baseline_file=app.config["BASELINE_FILE"],
                current_file=app.config["CURRENT_FILE"],
            )
            logs = get_audit_logs(log_file=app.config["LOG_FILE"], limit=10)
            backups = list_backups(backup_dir=app.config["BACKUP_DIR"])
            reports = list_reports(reports_dir=app.config["REPORTS_DIR"])

            return jsonify({
                "status": "success",
                "system_status": status_data["status"],
                "is_compliant": status_data["is_compliant"],
                "total_baseline_settings": status_data["total_baseline_settings"],
                "total_current_settings": status_data["total_current_settings"],
                "drift_count": status_data["drift_count"],
                "current_config": status_data["current_config"],
                "baseline_config": status_data["baseline_config"],
                "drift": status_data["drift"],
                "recent_logs": logs,
                "backup_count": len(backups),
                "report_count": len(reports),
            }), 200
        except Exception as error:
            return jsonify({
                "status": "error",
                "error": f"Failed to load dashboard data: {error}",
            }), 500

    @app.route("/api/configuration", methods=["GET"])
    def get_configuration():
        """3. Retrieve baseline and current test configuration."""
        try:
            baseline = load_baseline(baseline_file=app.config["BASELINE_FILE"])
            current = load_current_config(current_file=app.config["CURRENT_FILE"])

            # Build detailed comparison view
            all_keys = sorted(set(baseline.keys()) | set(current.keys()))
            settings = []
            for key in all_keys:
                expected = baseline.get(key, "<MISSING>")
                actual = current.get(key, "<MISSING>")
                settings.append({
                    "key": key,
                    "expected": expected,
                    "actual": actual,
                    "is_drifted": expected != actual,
                })

            return jsonify({
                "status": "success",
                "baseline": baseline,
                "current": current,
                "settings": settings,
                "total_settings": len(all_keys),
            }), 200
        except Exception as error:
            return jsonify({
                "status": "error",
                "error": f"Failed to retrieve configuration: {error}",
            }), 500

    @app.route("/api/drift", methods=["GET"])
    def get_drift():
        """4. Compare baseline and current configuration and return differences."""
        try:
            drift_issues = detect_drift(
                baseline_file=app.config["BASELINE_FILE"],
                current_file=app.config["CURRENT_FILE"],
                log_file=app.config["LOG_FILE"],
                record_log=False,
            )
            return jsonify({
                "status": "success",
                "drift_count": len(drift_issues),
                "is_compliant": len(drift_issues) == 0,
                "drift": [issue.to_dict() for issue in drift_issues],
            }), 200
        except Exception as error:
            return jsonify({
                "status": "error",
                "error": f"Failed to compute drift: {error}",
            }), 500

    @app.route("/api/drift/detect", methods=["POST"])
    def trigger_drift_detection():
        """11. Trigger a fresh drift scan, record to audit log, and return results."""
        try:
            drift_issues = detect_drift(
                baseline_file=app.config["BASELINE_FILE"],
                current_file=app.config["CURRENT_FILE"],
                log_file=app.config["LOG_FILE"],
                record_log=True,
            )

            # Auto-generate a report for this explicit scan
            report_status = "COMPLIANT" if not drift_issues else "NON-COMPLIANT"
            report_path = generate_report(
                status=report_status,
                issues=[issue.to_dict() for issue in drift_issues],
                repairs=[],
                reports_dir=app.config["REPORTS_DIR"],
            )

            return jsonify({
                "status": "success",
                "drift_count": len(drift_issues),
                "is_compliant": len(drift_issues) == 0,
                "compliance_status": report_status,
                "drift": [issue.to_dict() for issue in drift_issues],
                "report_generated": report_path.name,
            }), 200
        except Exception as error:
            return jsonify({
                "status": "error",
                "error": f"Failed to execute drift scan: {error}",
            }), 500

    @app.route("/api/drift/simulate", methods=["POST"])
    def post_simulate_drift():
        """5. Simulate drift in test configuration."""
        data = request.get_json(silent=True)
        if data is None or not isinstance(data, dict):
            return jsonify({
                "status": "error",
                "error": "Request body must be a valid JSON object.",
            }), 400

        with CONFIG_WRITE_LOCK:
            # Case A: Preset option specified (1 to 7)
            if "option" in data:
                opt = str(data["option"]).strip()
                if opt not in SIMULATION_PRESETS:
                    return jsonify({
                        "status": "error",
                        "error": f"Invalid simulation option '{opt}'. Must be one of: {list(SIMULATION_PRESETS.keys())}.",
                    }), 400

                try:
                    result = simulate_drift(
                        opt,
                        current_file=app.config["CURRENT_FILE"],
                        log_file=app.config["LOG_FILE"],
                    )
                    return jsonify({
                        "status": "success",
                        "message": "Drift simulation successfully applied.",
                        "simulation": result,
                    }), 200
                except Exception as error:
                    return jsonify({
                        "status": "error",
                        "error": f"Failed to simulate drift: {error}",
                    }), 500

            # Case B: Custom changes dictionary specified
            elif "changes" in data:
                changes = data["changes"]
                if not isinstance(changes, dict) or not changes:
                    return jsonify({
                        "status": "error",
                        "error": "The 'changes' field must be a non-empty JSON object.",
                    }), 400

                # Validate keys strictly against allowed configuration keys
                invalid_keys = set(changes.keys()) - ALLOWED_CONFIG_KEYS
                if invalid_keys:
                    return jsonify({
                        "status": "error",
                        "error": f"Disallowed configuration key(s): {sorted(invalid_keys)}. Permitted keys: {sorted(ALLOWED_CONFIG_KEYS)}",
                    }), 400

                try:
                    current = load_current_config(current_file=app.config["CURRENT_FILE"])
                    current.update(changes)
                    is_valid, validation_err = validate_config(current)
                    if not is_valid:
                        return jsonify({
                            "status": "error",
                            "error": f"Configuration validation failed: {validation_err}",
                        }), 400

                    save_json_atomic(app.config["CURRENT_FILE"], current)
                    log_event(
                        f"Custom drift simulated for keys: {list(changes.keys())}.",
                        log_file=app.config["LOG_FILE"],
                    )

                    return jsonify({
                        "status": "success",
                        "message": "Custom drift successfully applied.",
                        "applied_changes": changes,
                        "updated_config": current,
                    }), 200
                except Exception as error:
                    return jsonify({
                        "status": "error",
                        "error": f"Failed to apply custom drift: {error}",
                    }), 500

            else:
                return jsonify({
                    "status": "error",
                    "error": "Request body must contain either 'option' (1-7) or 'changes' object.",
                }), 400

    @app.route("/api/repair", methods=["POST"])
    def post_repair():
        """6. Repair test configuration with pre-backup and post-verification."""
        data = request.get_json(silent=True)
        if data is None or not isinstance(data, dict):
            return jsonify({
                "status": "error",
                "error": "Request body must be a valid JSON object.",
            }), 400

        # Require explicit confirmation
        if not data.get("confirm", False):
            return jsonify({
                "status": "error",
                "error": "Explicit confirmation required. Set 'confirm': true in request body.",
            }), 400

        with CONFIG_WRITE_LOCK:
            try:
                result = repair_configuration(
                    baseline_file=app.config["BASELINE_FILE"],
                    current_file=app.config["CURRENT_FILE"],
                    backup_dir=app.config["BACKUP_DIR"],
                    log_file=app.config["LOG_FILE"],
                    create_backup_first=True,
                )

                # Generate a repair report
                if result.get("repaired"):
                    report_path = generate_report(
                        status="COMPLIANT" if result["verified"] else "NON-COMPLIANT",
                        issues=result.get("repaired_issues", []),
                        repairs=[{"action": "restored_to_baseline", "issues": result.get("repaired_issues", [])}],
                        reports_dir=app.config["REPORTS_DIR"],
                    )
                    result["report_generated"] = report_path.name

                return jsonify({
                    "status": "success",
                    "repair_result": result,
                }), 200
            except Exception as error:
                return jsonify({
                    "status": "error",
                    "error": f"Failed to execute repair: {error}",
                }), 500

    @app.route("/api/logs", methods=["GET"])
    def get_logs():
        """7. Return recent audit log entries."""
        limit_arg = request.args.get("limit", default=100, type=int)
        lines = get_audit_logs(log_file=app.config["LOG_FILE"], limit=limit_arg)
        return jsonify({
            "status": "success",
            "count": len(lines),
            "logs": lines,
        }), 200

    @app.route("/api/reports", methods=["GET"])
    def get_reports():
        """8. List historical drift reports."""
        reports = list_reports(reports_dir=app.config["REPORTS_DIR"])
        return jsonify({
            "status": "success",
            "count": len(reports),
            "reports": reports,
        }), 200

    @app.route("/api/reports/<filename>", methods=["GET"])
    def get_single_report(filename: str):
        """Retrieve a specific report by filename with directory traversal security."""
        reports_dir = Path(app.config["REPORTS_DIR"]).resolve()
        safe_path = (reports_dir / filename).resolve()

        # Strict security check against path traversal
        if safe_path.parent != reports_dir or not safe_path.exists() or not safe_path.is_file():
            return jsonify({
                "status": "error",
                "error": "Report file not found or invalid filename.",
            }), 404

        try:
            report_data = load_json(safe_path)
            return jsonify({
                "status": "success",
                "filename": filename,
                "report": report_data,
            }), 200
        except Exception as error:
            return jsonify({
                "status": "error",
                "error": f"Failed to read report: {error}",
            }), 500

    @app.route("/api/backups", methods=["GET"])
    def get_backups():
        """9. List available configuration backups."""
        backups = list_backups(backup_dir=app.config["BACKUP_DIR"])
        return jsonify({
            "status": "success",
            "count": len(backups),
            "backups": backups,
        }), 200

    @app.route("/api/backups/restore", methods=["POST"])
    def post_restore_backup():
        """10. Restore a selected backup with confirmation and traversal validation."""
        data = request.get_json(silent=True)
        if data is None or not isinstance(data, dict):
            return jsonify({
                "status": "error",
                "error": "Request body must be a valid JSON object.",
            }), 400

        if not data.get("confirm", False):
            return jsonify({
                "status": "error",
                "error": "Explicit confirmation required. Set 'confirm': true in request body.",
            }), 400

        filename = data.get("filename")
        if not filename or not isinstance(filename, str):
            return jsonify({
                "status": "error",
                "error": "Field 'filename' is required.",
            }), 400

        # Enforce that filename is just a filename (no directory slashes allowed)
        if "/" in filename or "\\" in filename or ".." in filename:
            return jsonify({
                "status": "error",
                "error": "Invalid filename. Path traversal is strictly prohibited.",
            }), 400

        backup_dir = Path(app.config["BACKUP_DIR"]).resolve()
        target_path = (backup_dir / filename).resolve()

        if target_path.parent != backup_dir or not target_path.exists() or not target_path.is_file():
            return jsonify({
                "status": "error",
                "error": f"Backup file '{filename}' does not exist in backups directory.",
            }), 404

        with CONFIG_WRITE_LOCK:
            try:
                result = restore_backup(
                    target_path,
                    target_file=app.config["CURRENT_FILE"],
                    backup_dir=app.config["BACKUP_DIR"],
                    log_file=app.config["LOG_FILE"],
                )
                return jsonify({
                    "status": "success",
                    "message": f"Successfully restored configuration from {filename}.",
                    "restore_result": result,
                }), 200
            except Exception as error:
                return jsonify({
                    "status": "error",
                    "error": f"Failed to restore backup: {error}",
                }), 500

    return app


app = create_app()

if __name__ == "__main__":
    print("\nStarting Linux Drift Detection Web API on http://127.0.0.1:5000")
    print("Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=5000, debug=False)
