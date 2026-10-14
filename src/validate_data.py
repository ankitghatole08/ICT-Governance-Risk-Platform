
from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


REQUIRED_COLUMNS = {
    "assets.csv": {
        "asset_id",
        "asset_name",
        "asset_type",
        "business_service",
        "environment",
        "criticality",
        "owner",
        "internet_exposed",
        "data_classification",
        "created_date",
    },
    "ict_controls.csv": {
        "control_id",
        "control_name",
        "control_domain",
        "requirement",
        "control_owner",
        "frequency",
        "effectiveness_status",
        "last_tested_date",
    },
    "security_findings.csv": {
        "finding_id",
        "asset_id",
        "control_id",
        "title",
        "finding_type",
        "severity",
        "cvss_score",
        "discovered_date",
        "due_date",
        "status",
        "source",
        "description",
    },
    "remediation_actions.csv": {
        "action_id",
        "finding_id",
        "assigned_to",
        "action_title",
        "priority",
        "status",
        "created_date",
        "due_date",
        "completed_date",
        "evidence_reference",
        "comments",
    },
}


def load_dataset(filename: str) -> pd.DataFrame:
    """Load a CSV file or raise a clear error."""
    path = RAW_DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}\n"
            "Run 'python -m src.generate_data' first."
        )

    return pd.read_csv(path)


def check_columns(
    filename: str,
    dataframe: pd.DataFrame,
    errors: list[str],
) -> None:
    """Check whether the expected columns exist."""
    missing = REQUIRED_COLUMNS[filename] - set(dataframe.columns)

    if missing:
        errors.append(
            f"{filename}: missing columns: {sorted(missing)}"
        )


def check_primary_key(
    filename: str,
    dataframe: pd.DataFrame,
    column: str,
    errors: list[str],
) -> None:
    """Check primary keys for missing or duplicate values."""
    if column not in dataframe.columns:
        return

    if dataframe[column].isna().any():
        errors.append(f"{filename}: {column} contains missing values")

    if dataframe[column].duplicated().any():
        errors.append(f"{filename}: {column} contains duplicates")


def check_foreign_key(
    source_name: str,
    source_df: pd.DataFrame,
    source_column: str,
    target_name: str,
    target_df: pd.DataFrame,
    target_column: str,
    errors: list[str],
) -> None:
    """Check that every non-empty foreign key references a real row."""
    if source_column not in source_df.columns:
        return

    if target_column not in target_df.columns:
        return

    invalid_values = (
        set(source_df[source_column].dropna())
        - set(target_df[target_column].dropna())
    )

    if invalid_values:
        examples = sorted(invalid_values)[:5]
        errors.append(
            f"{source_name}.{source_column} references unknown "
            f"{target_name}.{target_column} values: {examples}"
        )


def check_date_column(
    filename: str,
    dataframe: pd.DataFrame,
    column: str,
    errors: list[str],
    allow_missing: bool = False,
) -> None:
    """Check whether a date column contains valid dates."""
    if column not in dataframe.columns:
        return

    values = dataframe[column]

    if not allow_missing and values.isna().any():
        errors.append(
            f"{filename}: {column} contains missing dates"
        )

    parsed = pd.to_datetime(values, errors="coerce")

    invalid = values.notna() & parsed.isna()

    if invalid.any():
        errors.append(
            f"{filename}: {column} contains invalid date values"
        )


def main() -> None:
    """Run Phase 1 data-quality checks."""
    errors: list[str] = []

    filenames = list(REQUIRED_COLUMNS)

    print("ICT Governance Platform - Data Validation")
    print("=" * 48)

    try:
        datasets = {
            filename: load_dataset(filename)
            for filename in filenames
        }
    except (FileNotFoundError, pd.errors.ParserError) as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(1) from exc

    # Check required columns and basic missing values.
    for filename, dataframe in datasets.items():
        check_columns(filename, dataframe, errors)

        print(
            f"Loaded {filename}: "
            f"{len(dataframe)} rows, {len(dataframe.columns)} columns"
        )

    # Primary-key checks.
    primary_keys = {
        "assets.csv": "asset_id",
        "ict_controls.csv": "control_id",
        "security_findings.csv": "finding_id",
        "remediation_actions.csv": "action_id",
    }

    for filename, column in primary_keys.items():
        check_primary_key(
            filename,
            datasets[filename],
            column,
            errors,
        )

    # Foreign-key checks.
    check_foreign_key(
        "security_findings.csv",
        datasets["security_findings.csv"],
        "asset_id",
        "assets.csv",
        datasets["assets.csv"],
        "asset_id",
        errors,
    )

    check_foreign_key(
        "security_findings.csv",
        datasets["security_findings.csv"],
        "control_id",
        "ict_controls.csv",
        datasets["ict_controls.csv"],
        "control_id",
        errors,
    )

    check_foreign_key(
        "remediation_actions.csv",
        datasets["remediation_actions.csv"],
        "finding_id",
        "security_findings.csv",
        datasets["security_findings.csv"],
        "finding_id",
        errors,
    )

    # CVSS score range.
    findings = datasets["security_findings.csv"]

    if "cvss_score" in findings.columns:
        scores = pd.to_numeric(
            findings["cvss_score"],
            errors="coerce",
        )

        if scores.isna().any():
            errors.append("security_findings.csv: invalid CVSS scores")
        elif not scores.between(0.0, 10.0).all():
            errors.append(
                "security_findings.csv: CVSS scores must be between 0 and 10"
            )

    # Date format checks.
    date_columns = {
        "assets.csv": ["created_date"],
        "ict_controls.csv": ["last_tested_date"],
        "security_findings.csv": ["discovered_date", "due_date"],
        "remediation_actions.csv": [
            "created_date",
            "due_date",
            "completed_date",
        ],
    }

    for filename, columns in date_columns.items():
        for column in columns:
            check_date_column(
                filename,
                datasets[filename],
                column,
                errors,
                allow_missing=(column == "completed_date"),
            )

    # Findings should have due dates on or after discovery.
    if {"discovered_date", "due_date"}.issubset(findings.columns):
        discovered = pd.to_datetime(
            findings["discovered_date"],
            errors="coerce",
        )
        due = pd.to_datetime(
            findings["due_date"],
            errors="coerce",
        )

        if (due < discovered).fillna(False).any():
            errors.append(
                "security_findings.csv: due date precedes discovery date"
            )

    # Completed actions should have a completion date.
    actions = datasets["remediation_actions.csv"]

    if {"status", "completed_date"}.issubset(actions.columns):
        completed_without_date = (
            actions["status"].eq("Completed")
            & actions["completed_date"].isna()
        )

        if completed_without_date.any():
            errors.append(
                "remediation_actions.csv: completed actions "
                "must have a completed_date"
            )

        incomplete_with_date = (
            ~actions["status"].eq("Completed")
            & actions["completed_date"].notna()
        )

        if incomplete_with_date.any():
            errors.append(
                "remediation_actions.csv: non-completed actions "
                "must not have a completed_date"
            )

    print("\nValidation results")
    print("-" * 48)

    if errors:
        for number, error in enumerate(errors, start=1):
            print(f"{number}. ERROR: {error}")

        print(f"\nFAILED: {len(errors)} validation issue(s) found.")
        raise SystemExit(1)

    print("PASS: All Phase 1 validation checks passed.")
    print("Primary keys are unique and foreign keys are valid.")
    print("Date fields and CVSS scores passed validation.")


if __name__ == "__main__":
    main()
