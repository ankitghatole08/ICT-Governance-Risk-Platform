
import csv
from pathlib import Path

import msal
import requests

BASE = "https://org565debe8.crm4.dynamics.com"
API = BASE + "/api/data/v9.2"
CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "ict_controls.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "missing_ict_controls.csv"

app = msal.PublicClientApplication(
    CLIENT_ID,
    authority="https://login.microsoftonline.com/organizations"
)

result = app.acquire_token_interactive(
    scopes=[BASE + "/user_impersonation"],
    port=8400
)

if "access_token" not in result:
    raise RuntimeError(
        result.get("error_description", "Authentication failed")
    )

session = requests.Session()
session.headers.update({
    "Authorization": "Bearer " + result["access_token"],
    "Accept": "application/json",
    "OData-Version": "4.0",
    "OData-MaxVersion": "4.0"
})


def get_json(url):
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def get_all(url):
    records = []

    while url:
        data = get_json(url)
        records.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return records


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    metadata = get_json(
        f"{API}/EntityDefinitions(LogicalName='cr7db_ictcontrol')"
        "?$select=EntitySetName"
    )

    entity_set = metadata["EntitySetName"]

    existing = get_all(
        f"{API}/{entity_set}"
        "?$select=cr7db_controlbusinessid"
    )

    existing_ids = {
        str(row.get("cr7db_controlbusinessid") or "").strip()
        for row in existing
    }

    with INPUT_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames
        source_rows = list(reader)

    if not columns or "control_id" not in columns:
        raise RuntimeError(
            "CSV must contain a control_id column."
        )

    missing_rows = [
        row for row in source_rows
        if row["control_id"].strip() not in existing_ids
    ]

    with OUTPUT_FILE.open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(missing_rows)

    print("\nICT CONTROL CHECK")
    print("-------------------------")
    print("Controls in original CSV:", len(source_rows))
    print("Controls in Dataverse:", len(existing))
    print("Missing controls:", len(missing_rows))

    print("\nMissing IDs:")
    for row in missing_rows:
        print(" -", row["control_id"])

    print("\nMissing-record CSV created:")
    print(OUTPUT_FILE)
    print("\nNo Dataverse records were changed.")


if __name__ == "__main__":
    main()
