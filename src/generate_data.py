
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------
# Project configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

RANDOM_SEED = 42
TODAY = date.today()

random.seed(RANDOM_SEED)

SEVERITIES = ["Critical", "High", "Medium", "Low"]
SEVERITY_WEIGHTS = [10, 30, 40, 20]

SEVERITY_CVSS_RANGES = {
    "Critical": (9.0, 10.0),
    "High": (7.0, 8.9),
    "Medium": (4.0, 6.9),
    "Low": (0.1, 3.9),
}

SEVERITY_SLA_DAYS = {
    "Critical": 7,
    "High": 30,
    "Medium": 60,
    "Low": 90,
}


def random_past_date(max_days_ago: int = 180) -> date:
    """Return a reproducible date within the previous max_days_ago days."""
    days_ago = random.randint(0, max_days_ago)
    return TODAY - timedelta(days=days_ago)


def random_date_between(start: date, end: date) -> date:
    """Return a random date between two dates, inclusive."""
    if start > end:
        start, end = end, start

    days_between = (end - start).days
    return start + timedelta(days=random.randint(0, days_between))


def build_assets(count: int = 30) -> pd.DataFrame:
    """Create synthetic IT assets."""
    asset_types = [
        "Web Application",
        "Database",
        "API",
        "Cloud Service",
        "Virtual Machine",
        "Business Application",
    ]

    services = [
        "Payments",
        "Trading Operations",
        "Customer Management",
        "Risk Management",
        "Data Analytics",
        "Identity Management",
    ]

    criticalities = ["Critical", "High", "Medium", "Low"]
    criticality_weights = [15, 35, 35, 15]

    environments = ["Production", "Pre-Production", "Development"]
    environment_weights = [60, 20, 20]

    classifications = [
        "Public",
        "Internal",
        "Confidential",
        "Restricted",
    ]

    rows = []

    for number in range(1, count + 1):
        asset_type = random.choice(asset_types)
        criticality = random.choices(
            criticalities,
            weights=criticality_weights,
            k=1,
        )[0]

        rows.append(
            {
                "asset_id": f"AST-{number:04d}",
                "asset_name": f"Synthetic {asset_type} {number:02d}",
                "asset_type": asset_type,
                "business_service": random.choice(services),
                "environment": random.choices(
                    environments,
                    weights=environment_weights,
                    k=1,
                )[0],
                "criticality": criticality,
                "owner": f"Team-{random.randint(1, 8):02d}",
                "internet_exposed": random.choice([True, False]),
                "data_classification": random.choice(classifications),
                "created_date": random_past_date().isoformat(),
            }
        )

    return pd.DataFrame(rows)


def build_controls(count: int = 15) -> pd.DataFrame:
    """Create synthetic ICT governance and security controls."""
    control_templates = [
        (
            "Access Management",
            "Privileged access must be reviewed periodically.",
            "Monthly",
        ),
        (
            "Vulnerability Management",
            "Security findings must be assessed and remediated within SLA.",
            "Weekly",
        ),
        (
            "Patch Management",
            "Supported systems must receive security patches.",
            "Monthly",
        ),
        (
            "Logging and Monitoring",
            "Critical systems must generate reviewable security logs.",
            "Monthly",
        ),
        (
            "Backup and Recovery",
            "Critical data must have tested recovery arrangements.",
            "Quarterly",
        ),
        (
            "Change Management",
            "Material changes must have documented approval.",
            "Monthly",
        ),
        (
            "Incident Management",
            "Security incidents must be recorded and investigated.",
            "Monthly",
        ),
        (
            "Data Protection",
            "Sensitive data must have appropriate access restrictions.",
            "Quarterly",
        ),
        (
            "Asset Management",
            "Technology assets must have accountable owners.",
            "Quarterly",
        ),
        (
            "Third-Party Risk",
            "Relevant third-party risks must be reviewed.",
            "Annually",
        ),
    ]

    effectiveness_statuses = [
        "Effective",
        "Needs Improvement",
        "Ineffective",
        "Not Tested",
    ]

    rows = []

    for number in range(1, count + 1):
        domain, requirement, frequency = control_templates[
            (number - 1) % len(control_templates)
        ]

        last_tested = random_past_date(120)

        rows.append(
            {
                "control_id": f"CTL-{number:04d}",
                "control_name": f"{domain} Control {number:02d}",
                "control_domain": domain,
                "requirement": requirement,
                "control_owner": f"Governance-Team-{random.randint(1, 4)}",
                "frequency": frequency,
                "effectiveness_status": random.choice(
                    effectiveness_statuses
                ),
                "last_tested_date": last_tested.isoformat(),
            }
        )

    return pd.DataFrame(rows)


def build_findings(
    assets: pd.DataFrame,
    controls: pd.DataFrame,
    count: int = 100,
) -> pd.DataFrame:
    """Create synthetic security findings linked to assets and controls."""
    finding_types = [
        "Missing Security Patch",
        "Weak Access Configuration",
        "Misconfiguration",
        "Outdated Software",
        "Insufficient Logging",
        "Encryption Gap",
        "Unsupported Component",
    ]

    statuses = [
        "Open",
        "In Progress",
        "Resolved",
        "Accepted Risk",
    ]

    status_weights = [35, 35, 25, 5]

    sources = [
        "Vulnerability Scanner",
        "Configuration Review",
        "Control Assessment",
        "Internal Audit",
    ]

    asset_ids = assets["asset_id"].tolist()
    control_ids = controls["control_id"].tolist()

    rows = []

    for number in range(1, count + 1):
        severity = random.choices(
            SEVERITIES,
            weights=SEVERITY_WEIGHTS,
            k=1,
        )[0]

        cvss_min, cvss_max = SEVERITY_CVSS_RANGES[severity]
        cvss_score = round(random.uniform(cvss_min, cvss_max), 1)

        discovered = random_past_date(150)
        due_date = discovered + timedelta(
            days=SEVERITY_SLA_DAYS[severity]
        )

        status = random.choices(
            statuses,
            weights=status_weights,
            k=1,
        )[0]

        rows.append(
            {
                "finding_id": f"FND-{number:05d}",
                "asset_id": random.choice(asset_ids),
                "control_id": random.choice(control_ids),
                "title": (
                    f"{severity} - "
                    f"{random.choice(finding_types)} - "
                    f"Finding {number:03d}"
                ),
                "finding_type": random.choice(finding_types),
                "severity": severity,
                "cvss_score": cvss_score,
                "discovered_date": discovered.isoformat(),
                "due_date": due_date.isoformat(),
                "status": status,
                "source": random.choice(sources),
                "description": (
                    "Synthetic demonstration finding. "
                    "No real system or vulnerability is represented."
                ),
            }
        )

    return pd.DataFrame(rows)


def build_remediation_actions(
    findings: pd.DataFrame,
) -> pd.DataFrame:
    """Create one or more remediation actions for each finding."""
    statuses = ["Planned", "In Progress", "Blocked", "Completed"]
    status_weights = [20, 30, 10, 40]

    action_templates = [
        "Review the affected configuration",
        "Apply the required security update",
        "Validate access permissions",
        "Collect remediation evidence",
        "Perform a verification scan",
        "Update the control documentation",
    ]

    rows = []
    action_number = 1

    for finding in findings.to_dict(orient="records"):
        # Every finding receives at least one remediation action.
        action_count = random.choices(
            [1, 2],
            weights=[75, 25],
            k=1,
        )[0]

        finding_due = date.fromisoformat(finding["due_date"])
        discovered = date.fromisoformat(finding["discovered_date"])

        for _ in range(action_count):
            created = random_date_between(discovered, TODAY)

            status = random.choices(
                statuses,
                weights=status_weights,
                k=1,
            )[0]

            completed_date = None

            if status == "Completed":
                completed_date = random_date_between(created, TODAY)

            rows.append(
                {
                    "action_id": f"ACT-{action_number:05d}",
                    "finding_id": finding["finding_id"],
                    "assigned_to": (
                        f"Remediation-Team-{random.randint(1, 8)}"
                    ),
                    "action_title": random.choice(action_templates),
                    "priority": finding["severity"],
                    "status": status,
                    "created_date": created.isoformat(),
                    "due_date": finding_due.isoformat(),
                    "completed_date": (
                        completed_date.isoformat()
                        if completed_date
                        else None
                    ),
                    "evidence_reference": (
                        f"SYNTHETIC-EVIDENCE-{action_number:05d}"
                        if status == "Completed"
                        else None
                    ),
                    "comments": (
                        "Synthetic demonstration record; "
                        "evidence is not a real document."
                    ),
                }
            )

            action_number += 1

    return pd.DataFrame(rows)


def main() -> None:
    """Generate all Phase 1 datasets."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    assets = build_assets()
    controls = build_controls()
    findings = build_findings(assets, controls)
    actions = build_remediation_actions(findings)

    datasets = {
        "assets.csv": assets,
        "ict_controls.csv": controls,
        "security_findings.csv": findings,
        "remediation_actions.csv": actions,
    }

    print("Generating synthetic ICT governance datasets...\n")

    for filename, dataframe in datasets.items():
        output_path = RAW_DATA_DIR / filename
        dataframe.to_csv(output_path, index=False)

        print(
            f"Created: {output_path.relative_to(PROJECT_ROOT)} "
            f"({len(dataframe)} rows)"
        )

    print("\nData generation completed.")
    print("All records are synthetic and intended for demonstration.")


if __name__ == "__main__":
    main()
