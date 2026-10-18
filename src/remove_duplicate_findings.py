
from collections import defaultdict
from pathlib import Path
import csv
import msal
import requests

BASE = "https://org565debe8.crm4.dynamics.com"
API = BASE + "/api/data/v9.2"
CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"

# Automatically delete verified duplicates
DELETE_DUPLICATES = True

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

    if not response.ok:
        raise RuntimeError(
            f"GET failed ({response.status_code}): {response.text}"
        )

    return response.json()


def get_metadata(logical_name):
    return get_json(
        f"{API}/EntityDefinitions(LogicalName='{logical_name}')"
        "?$select=EntitySetName,PrimaryIdAttribute"
    )


def get_all(url):
    records = []

    while url:
        data = get_json(url)
        records.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return records


def main():
    finding_meta = get_metadata("ict_securityfinding")
    action_meta = get_metadata("ict_remediationaction")

    finding_set = finding_meta["EntitySetName"]
    finding_pk = finding_meta["PrimaryIdAttribute"]
    action_set = action_meta["EntitySetName"]

    findings = get_all(
        f"{API}/{finding_set}"
        f"?$select={finding_pk},ict_findingbusinessid,createdon"
    )

    actions = get_all(
        f"{API}/{action_set}"
        "?$select=_ict_securityfinding_value"
    )

    linked_finding_ids = {
        str(row["_ict_securityfinding_value"]).lower()
        for row in actions
        if row.get("_ict_securityfinding_value")
    }

    groups = defaultdict(list)

    for record in findings:
        business_id = str(
            record.get("ict_findingbusinessid") or ""
        ).strip()

        if business_id:
            groups[business_id].append(record)

    duplicates_to_delete = []
    blocked = []

    for business_id, records in sorted(groups.items()):

        # Keep a linked record if one exists.
        # Otherwise keep the oldest record.
        records.sort(
            key=lambda r: (
                str(r[finding_pk]).lower()
                not in linked_finding_ids,
                r.get("createdon") or "",
                str(r[finding_pk])
            )
        )

        for record in records[1:]:
            record_id = str(record[finding_pk]).lower()

            if record_id in linked_finding_ids:
                blocked.append((business_id, record_id))
            else:
                duplicates_to_delete.append(
                    (business_id, record_id)
                )

    print("\nDUPLICATE CLEANUP REPORT")
    print("------------------------")
    print("Total Security Findings:", len(findings))
    print("Unique Finding Business IDs:", len(groups))
    print("Remediation Actions:", len(actions))
    print("Findings linked to actions:", len(linked_finding_ids))
    print(
        "Duplicates eligible for deletion:",
        len(duplicates_to_delete)
    )
    print("Blocked linked duplicates:", len(blocked))

    report_path = Path("duplicate_cleanup_preview.csv")

    with report_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["business_id", "dataverse_guid"])
        writer.writerows(duplicates_to_delete)

    print("\nCleanup report saved:", report_path.resolve())

    if blocked:
        raise RuntimeError(
            "Cleanup stopped: some duplicates are linked "
            "to Remediation Actions."
        )

    # Protect against unexpected data changes
    if len(groups) != 100:
        raise RuntimeError(
            "Expected 100 unique business IDs. "
            "Cleanup cancelled."
        )

    if len(findings) != 227:
        raise RuntimeError(
            "Expected 227 records. "
            "Cleanup cancelled."
        )

    if len(duplicates_to_delete) != 127:
        raise RuntimeError(
            "Expected exactly 127 duplicates. "
            "Cleanup cancelled."
        )

    if not DELETE_DUPLICATES:
        print("\nPreview mode. No records deleted.")
        return

    print("\nDeleting 127 duplicate records automatically...\n")

    deleted = 0

    for business_id, record_id in duplicates_to_delete:

        response = session.delete(
            f"{API}/{finding_set}({record_id})",
            timeout=60
        )

        if response.status_code not in (200, 204):
            raise RuntimeError(
                f"Deletion failed for {business_id} "
                f"({record_id}): "
                f"{response.status_code} {response.text}"
            )

        deleted += 1

        print(
            f"Deleted {deleted}/127: {business_id}"
        )

    print("\nVerifying remaining records...")

    remaining = get_all(
        f"{API}/{finding_set}"
        f"?$select={finding_pk},ict_findingbusinessid"
    )

    remaining_ids = [
        str(row.get("ict_findingbusinessid") or "").strip()
        for row in remaining
    ]

    print("\nCLEANUP RESULTS")
    print("------------------------")
    print("Records deleted:", deleted)
    print("Records remaining:", len(remaining))
    print("Unique remaining IDs:", len(set(remaining_ids)))

    if len(remaining) == 100 and len(set(remaining_ids)) == 100:
        print("\nSUCCESS: All duplicates removed!")
    else:
        print("\nWARNING: Remaining records need investigation.")


if __name__ == "__main__":
    main()
