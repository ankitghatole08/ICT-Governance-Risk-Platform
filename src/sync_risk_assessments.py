
"""Synchronize scored findings into Dataverse ICT Risk Assessment.

Default: read-only dry run.
Use --apply only after checking planned changes.

Requires requests and msal.
The ICT Risk Assessment table must already exist.
"""

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "processed" / "risk_scores.csv"

BASE = "https://org565debe8.crm4.dynamics.com"
API = BASE + "/api/data/v9.2"
CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"

COLUMN_TYPES = {
    "Assessment Title": "String",
    "Finding Business ID": "String",
    "Risk Score": "Integer",
    "Risk Level": "String",
    "Review Priority": "String",
    "Risk Explanation": "Memo",
    "Recommended Action": "Memo",
    "Assessment Date": "DateTime",
    "Outstanding Action Count": "Integer",
    "Overdue Action Count": "Integer",
}

CSV_FIELDS = {
    "finding_id",
    "risk_score",
    "risk_level",
    "review_priority",
    "risk_explanation",
    "recommended_action",
    "as_of_date",
    "outstanding_action_count",
    "overdue_action_count",
}


def load_scores():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Run risk_scoring.py first: {CSV_PATH}"
        )

    with CSV_PATH.open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        reader = csv.DictReader(handle)

        missing = CSV_FIELDS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"Missing risk score columns: {sorted(missing)}"
            )

        data = list(reader)

    if not data:
        raise ValueError("Risk scores CSV is empty")

    ids = set()

    for row in data:
        key = row["finding_id"].strip()

        if not key or key in ids:
            raise ValueError(
                f"Empty or duplicate finding ID: {key!r}"
            )

        ids.add(key)

        score = int(row["risk_score"])

        if not 0 <= score <= 100:
            raise ValueError(
                f"Invalid risk score for {key}: {score}"
            )

        if row["risk_level"] not in {
            "Critical", "High", "Medium", "Low"
        }:
            raise ValueError(
                f"Invalid risk level for {key}"
            )

        for field in (
            "outstanding_action_count",
            "overdue_action_count",
        ):
            if int(row[field]) < 0:
                raise ValueError(
                    f"Negative {field} for {key}"
                )

    return data


def make_payload(row, logical_names):
    values = {
        "Assessment Title":
            "Risk assessment - " + row["finding_id"].strip(),

        "Finding Business ID":
            row["finding_id"].strip(),

        "Risk Score":
            int(row["risk_score"]),

        "Risk Level":
            row["risk_level"].strip(),

        "Review Priority":
            row["review_priority"].strip(),

        "Risk Explanation":
            row["risk_explanation"].strip(),

        "Recommended Action":
            row["recommended_action"].strip(),

        "Assessment Date":
            row["as_of_date"].strip(),

        "Outstanding Action Count":
            int(row["outstanding_action_count"]),

        "Overdue Action Count":
            int(row["overdue_action_count"]),
    }

    return {
        logical_names[label]: value
        for label, value in values.items()
    }


def check(response):
    if not response.ok:
        raise RuntimeError(
            f"Dataverse HTTP {response.status_code}: "
            f"{response.text[:1200]}"
        )

    return response.json() if response.content else {}


def get_json(session, url):
    return check(session.get(url, timeout=60))


def paged_rows(session, url):
    result = []

    while url:
        content = get_json(session, url)
        result.extend(content.get("value", []))
        url = content.get("@odata.nextLink")

    return result


def connect():
    import msal
    import requests

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority="https://login.microsoftonline.com/organizations",
    )

    auth = app.acquire_token_interactive(
        scopes=[BASE + "/user_impersonation"],
        port=8400,
    )

    if "access_token" not in auth:
        raise RuntimeError(
            "Microsoft sign-in failed: "
            + str(auth.get("error_description"))
        )

    session = requests.Session()

    session.headers.update({
        "Authorization": "Bearer " + auth["access_token"],
        "Accept": "application/json",
        "Content-Type": "application/json",
        "OData-Version": "4.0",
        "OData-MaxVersion": "4.0",
    })

    return session


def display_labels(attribute):
    display = attribute.get("DisplayName") or {}

    return {
        label.get("Label", "").strip().casefold()
        for label in (
            display.get("LocalizedLabels") or []
        )
    }


def discover(session, logical_table):
    metadata = get_json(
        session,
        f"{API}/EntityDefinitions(LogicalName='{logical_table}')"
        "?$select=LogicalName,EntitySetName,PrimaryIdAttribute",
    )

    attributes = paged_rows(
        session,
        f"{API}/EntityDefinitions(LogicalName='{logical_table}')"
        "/Attributes"
        "?$select=LogicalName,DisplayName,AttributeType",
    )

    mapping = {}

    for label, expected_type in COLUMN_TYPES.items():
        matches = [
            attribute
            for attribute in attributes
            if label.casefold() in display_labels(attribute)
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one column named {label!r}; "
                f"found {len(matches)}. "
                "Verify the ICT Risk Assessment table columns."
            )

        attribute = matches[0]

        if attribute["AttributeType"] != expected_type:
            raise ValueError(
                f"{label} must be {expected_type}, "
                f"but Dataverse reports "
                f"{attribute['AttributeType']}"
            )

        mapping[label] = attribute["LogicalName"]

    return metadata, mapping


def existing_assessments(
    session, metadata, finding_col
):
    record_id = metadata["PrimaryIdAttribute"]

    rows = paged_rows(
        session,
        f"{API}/{metadata['EntitySetName']}"
        f"?$select={record_id},{finding_col}",
    )

    index = {}

    for row in rows:
        finding_id = (
            row.get(finding_col) or ""
        ).strip()

        if not finding_id:
            continue

        if finding_id in index:
            raise ValueError(
                "Dataverse has duplicate ICT Risk "
                f"Assessment records for {finding_id}. "
                "Resolve duplicates before syncing."
            )

        index[finding_id] = row[record_id]

    return index


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--table",
        default="ict_riskassessment",
        help="Actual Dataverse logical table name",
    )

    parser.add_argument(
        "--expected-count",
        type=int,
        default=100,
        help="Safety check for scored CSV record count",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create/update Dataverse records",
    )

    args = parser.parse_args()

    scored = load_scores()

    if (
        args.expected_count
        and len(scored) != args.expected_count
    ):
        raise ValueError(
            f"Expected {args.expected_count} findings, "
            f"found {len(scored)}. "
            "Check the input file before syncing."
        )

    print(
        f"Risk assessment CSV: "
        f"{len(scored)} valid findings"
    )

    session = connect()

    metadata, columns = discover(
        session, args.table
    )

    previous = existing_assessments(
        session,
        metadata,
        columns["Finding Business ID"],
    )

    creating = [
        row for row in scored
        if row["finding_id"] not in previous
    ]

    updating = [
        row for row in scored
        if row["finding_id"] in previous
    ]

    print(
        f"Dataverse table: "
        f"{metadata['LogicalName']}"
    )

    print(
        f"Planned: CREATE {len(creating)}; "
        f"UPDATE {len(updating)}"
    )

    for row in scored[:3]:
        print(
            f"  Preview: {row['finding_id']} -> "
            f"{row['risk_score']}/100, "
            f"{row['review_priority']}"
        )

    if not args.apply:
        print(
            "DRY RUN ONLY: no Dataverse "
            "records were changed."
        )
        print(
            "Review results, then rerun with "
            "--apply when ready."
        )
        return

    entity_set = metadata["EntitySetName"]

    for number, row in enumerate(scored, start=1):
        payload = make_payload(row, columns)
        existing_guid = previous.get(
            row["finding_id"]
        )

        if existing_guid:
            url = (
                f"{API}/{entity_set}"
                f"({existing_guid})"
            )

            check(
                session.patch(
                    url,
                    json=payload,
                    timeout=60,
                )
            )

        else:
            url = f"{API}/{entity_set}"

            check(
                session.post(
                    url,
                    json=payload,
                    timeout=60,
                )
            )

        if (
            number % 20 == 0
            or number == len(scored)
        ):
            print(
                f"Synchronized "
                f"{number}/{len(scored)}"
            )

    print(
        "SUCCESS: Risk assessments synchronized. "
        "No source findings were changed."
    )


if __name__ == "__main__":
    main()
