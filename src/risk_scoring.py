
"""Explainable, rule-based ICT finding risk scoring (synthetic prototype)."""

import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "raw"
OUTPUT_FILE = ROOT / "data" / "processed" / "risk_scores.csv"

REQUIRED_COLUMNS = {
    "assets.csv": {
        "asset_id", "asset_name", "criticality", "internet_exposed"
    },
    "ict_controls.csv": {
        "control_id", "control_name", "effectiveness_status"
    },
    "security_findings.csv": {
        "finding_id", "asset_id", "control_id",
        "title", "severity", "status"
    },
    "remediation_actions.csv": {
        "action_id", "finding_id", "status", "due_date"
    },
}

SEVERITY_POINTS = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
}

CRITICALITY_POINTS = {
    "critical": 20,
    "high": 15,
    "medium": 10,
    "low": 5,
}

CONTROL_POINTS = {
    "ineffective": 15,
    "needs improvement": 12,
    "not tested": 10,
    "effective": 0,
}

COMPLETE_STATUSES = {"completed"}

VALID_ACTION_STATUSES = {
    "open", "in progress", "blocked", "completed"
}

CLOSED_FINDING_STATUSES = {
    "resolved", "closed", "completed"
}

TRUE_VALUES = {"yes", "true", "1", "y"}
FALSE_VALUES = {"no", "false", "0", "n"}


def normalized(value):
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("_", " ")
        .split()
    )


def read_table(filename):
    path = INPUT_DIR / filename

    if not path.is_file():
        raise FileNotFoundError(f"Missing input CSV: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        headers = set(reader.fieldnames or [])

        missing = REQUIRED_COLUMNS[filename] - headers

        if missing:
            raise ValueError(
                f"{filename} is missing columns: {sorted(missing)}"
            )

        return [
            {
                key: (value or "").strip()
                for key, value in row.items()
            }
            for row in reader
        ]


def build_index(rows, id_col, filename):
    indexed = {}

    for line_number, row in enumerate(rows, 2):
        business_id = row[id_col]

        if not business_id:
            raise ValueError(
                f"{filename}, line {line_number}: empty {id_col}"
            )

        if business_id in indexed:
            raise ValueError(
                f"{filename}: duplicate {id_col} = {business_id}"
            )

        indexed[business_id] = row

    return indexed


def points_for(value, lookup, field_name, business_id):
    key = normalized(value)

    if key not in lookup:
        raise ValueError(
            f"Unknown {field_name}={value!r} for {business_id}; "
            f"expected one of: {', '.join(lookup)}"
        )

    return lookup[key]


def parse_exposure(value, asset_id):
    key = normalized(value)

    if key in TRUE_VALUES:
        return True

    if key in FALSE_VALUES:
        return False

    raise ValueError(
        f"Unknown internet_exposed={value!r} for {asset_id}"
    )


def parse_optional_date(value, action_id):
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])

    except ValueError as error:
        raise ValueError(
            f"Invalid due_date={value!r} for {action_id}"
        ) from error


def categorize(score):
    if score >= 80:
        return "Critical", "P1 - Immediate review"

    if score >= 60:
        return "High", "P2 - High priority"

    if score >= 40:
        return "Medium", "P3 - Planned review"

    return "Low", "P4 - Monitor"


def score_finding(finding, asset, control, actions, as_of):
    finding_id = finding["finding_id"]

    sev_score = points_for(
        finding["severity"],
        SEVERITY_POINTS,
        "severity",
        finding_id,
    )

    asset_score = points_for(
        asset["criticality"],
        CRITICALITY_POINTS,
        "asset criticality",
        asset["asset_id"],
    )

    control_score = points_for(
        control["effectiveness_status"],
        CONTROL_POINTS,
        "control effectiveness",
        control["control_id"],
    )

    exposed = parse_exposure(
        asset["internet_exposed"],
        asset["asset_id"],
    )

    exposure_score = 10 if exposed else 0

    outstanding = []
    overdue = []

    for action in actions:
        status = normalized(action["status"])

        if status not in VALID_ACTION_STATUSES:
            raise ValueError(
                f"Unknown remediation status={action['status']!r} "
                f"for {action['action_id']}"
            )

        due = parse_optional_date(
            action["due_date"],
            action["action_id"],
        )

        if status not in COMPLETE_STATUSES:
            outstanding.append((action, due))

            if due is not None and due < as_of:
                overdue.append(action)

    if overdue:
        remediation_score = 15
        remediation_reason = (
            f"{len(overdue)} overdue action(s)"
        )

    elif not actions:
        remediation_score = 12
        remediation_reason = "no remediation action assigned"

    elif outstanding:
        remediation_score = 7
        remediation_reason = (
            f"{len(outstanding)} outstanding action(s)"
        )

    else:
        remediation_score = 0
        remediation_reason = (
            "all remediation actions completed"
        )

    score = (
        sev_score
        + asset_score
        + control_score
        + remediation_score
        + exposure_score
    )

    level, priority = categorize(score)

    if normalized(finding["status"]) in CLOSED_FINDING_STATUSES:
        priority = "Historical - verify closure"

    outstanding_dates = [
        due for _, due in outstanding
        if due is not None
    ]

    next_due = (
        min(outstanding_dates)
        if outstanding_dates else None
    )

    explanation = (
        f"Severity {finding['severity']} (+{sev_score}); "
        f"asset criticality {asset['criticality']} (+{asset_score}); "
        f"control {control['effectiveness_status']} "
        f"(+{control_score}); "
        f"remediation: {remediation_reason} "
        f"(+{remediation_score}); "
        f"internet exposed: {'yes' if exposed else 'no'} "
        f"(+{exposure_score})."
    )

    recommendations = []

    if overdue:
        recommendations.append(
            "Escalate overdue actions to their assigned owners"
        )

    elif not actions:
        recommendations.append(
            "Create and assign a remediation action"
        )

    elif outstanding:
        recommendations.append(
            "Track outstanding remediation to closure"
        )

    if control_score:
        recommendations.append(
            "Review or strengthen the linked ICT control"
        )

    if exposed:
        recommendations.append(
            "Validate internet exposure and "
            "compensating protections"
        )

    if sev_score >= 30:
        recommendations.append(
            "Prioritize technical investigation of the finding"
        )

    if normalized(finding["status"]) in CLOSED_FINDING_STATUSES:
        recommendations.append(
            "Confirm closure evidence before reopening"
        )

    if not recommendations:
        recommendations.append(
            "Continue routine monitoring and control testing"
        )

    return {
        "finding_id": finding_id,
        "title": finding["title"],
        "finding_status": finding["status"],
        "asset_id": asset["asset_id"],
        "control_id": control["control_id"],
        "severity": finding["severity"],
        "asset_criticality": asset["criticality"],
        "control_effectiveness": control["effectiveness_status"],
        "internet_exposed": "Yes" if exposed else "No",
        "remediation_action_count": len(actions),
        "outstanding_action_count": len(outstanding),
        "overdue_action_count": len(overdue),
        "next_outstanding_due_date": (
            next_due.isoformat() if next_due else ""
        ),
        "severity_points": sev_score,
        "asset_criticality_points": asset_score,
        "control_effectiveness_points": control_score,
        "remediation_points": remediation_score,
        "internet_exposure_points": exposure_score,
        "risk_score": score,
        "risk_level": level,
        "review_priority": priority,
        "risk_explanation": explanation,
        "recommended_action": "; ".join(recommendations),
        "as_of_date": as_of.isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        help=(
            "Assessment date YYYY-MM-DD "
            "(defaults to today's local date)"
        ),
    )

    args = parser.parse_args()

    assets = build_index(
        read_table("assets.csv"),
        "asset_id",
        "assets.csv",
    )

    controls = build_index(
        read_table("ict_controls.csv"),
        "control_id",
        "ict_controls.csv",
    )

    findings = build_index(
        read_table("security_findings.csv"),
        "finding_id",
        "security_findings.csv",
    )

    actions = build_index(
        read_table("remediation_actions.csv"),
        "action_id",
        "remediation_actions.csv",
    )

    actions_by_finding = defaultdict(list)

    for action in actions.values():
        fid = action["finding_id"]

        if fid not in findings:
            raise ValueError(
                f"Action {action['action_id']} "
                f"references missing finding {fid}"
            )

        actions_by_finding[fid].append(action)

    results = []

    for finding in findings.values():
        fid = finding["finding_id"]

        asset_id = finding["asset_id"]
        control_id = finding["control_id"]

        if asset_id not in assets:
            raise ValueError(
                f"Finding {fid} references "
                f"missing asset {asset_id}"
            )

        if control_id not in controls:
            raise ValueError(
                f"Finding {fid} references "
                f"missing control {control_id}"
            )

        result = score_finding(
            finding,
            assets[asset_id],
            controls[control_id],
            actions_by_finding[fid],
            args.as_of,
        )

        results.append(result)

    results.sort(
        key=lambda row: (
            -row["risk_score"],
            row["finding_id"],
        )
    )

    if not results:
        raise ValueError(
            "No findings to score. No output written."
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0].keys()),
        )

        writer.writeheader()
        writer.writerows(results)

    print(f"Assessment date: {args.as_of}")

    print(
        f"Assets: {len(assets)} | "
        f"Controls: {len(controls)} | "
        f"Findings scored: {len(results)} | "
        f"Remediation actions: {len(actions)}"
    )

    for level in ("Critical", "High", "Medium", "Low"):
        count = sum(
            row["risk_level"] == level
            for row in results
        )

        print(f"{level}: {count}")

    print(f"Saved: {OUTPUT_FILE}")

    print("Top five findings:")

    for row in results[:5]:
        print(
            f"  {row['finding_id']}: "
            f"{row['risk_score']}/100 "
            f"({row['risk_level']}) - "
            f"{row['review_priority']}"
        )


if __name__ == "__main__":
    main()
