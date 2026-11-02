#!/usr/bin/env python3
"""Report generation utility for Linux Infrastructure Drift Detection & Auto Repair System."""

from pathlib import Path
from typing import Any, List, Optional

from core.drift_service import (
    REPORTS_DIR,
    generate_report as service_generate_report,
    list_reports as service_list_reports,
)

PROJECT_DIR = Path(__file__).resolve().parent


def generate_report(
    status: str = "COMPLIANT",
    issues: Optional[List[Any]] = None,
    repairs: Optional[List[Any]] = None,
    filename: Optional[str] = None,
) -> Path:
    """Generate a timestamped JSON drift detection report."""
    return service_generate_report(
        status=status,
        issues=issues,
        repairs=repairs,
        filename=filename,
        reports_dir=REPORTS_DIR,
    )


def list_reports() -> List[dict]:
    """List historical reports sorted newest first."""
    return service_list_reports(reports_dir=REPORTS_DIR)


if __name__ == "__main__":
    path = generate_report(
        status="COMPLIANT",
        issues=[],
        repairs=[],
    )
    print(f"Report generated successfully: {path}")
