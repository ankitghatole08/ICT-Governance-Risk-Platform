
from collections import defaultdict
import msal
import requests

BASE = "https://org565debe8.crm4.dynamics.com"
API = BASE + "/api/data/v9.2"

CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"

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

def fetch(url):
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return response.json()

# Discover the actual Dataverse entity set
meta = fetch(
    f"{API}/EntityDefinitions(LogicalName='ict_securityfinding')"
    "?$select=EntitySetName,PrimaryIdAttribute,PrimaryNameAttribute"
)

entity_set = meta["EntitySetName"]
id_field = meta["PrimaryIdAttribute"]
name_field = meta["PrimaryNameAttribute"]
business_field = "ict_findingbusinessid"

url = (
    f"{API}/{entity_set}"
    f"?$select={id_field},{business_field},{name_field}"
)

rows = []

while url:
    data = fetch(url)
    rows.extend(data.get("value", []))
    url = data.get("@odata.nextLink")

groups = defaultdict(list)

for row in rows:
    business_id = str(row.get(business_field) or "").strip()
    if business_id:
        groups[business_id].append(row)

duplicates = {
    key: records
    for key, records in groups.items()
    if len(records) > 1
}

print("\nSECURITY FINDING DUPLICATE REPORT")
print("--------------------------------")
print("Total Dataverse records:", len(rows))
print("Unique nonempty business IDs:", len(groups))
print("Duplicate business IDs:", len(duplicates))
print(
    "Extra duplicate records:",
    sum(len(records) - 1 for records in duplicates.values())
)

for business_id, records in sorted(duplicates.items()):
    print(f"\n{business_id}: {len(records)} records")
    for record in records:
        print(
            "  GUID:", record[id_field],
            "| Title:", record.get(name_field, "")
        )

print("\nREAD-ONLY CHECK COMPLETE. No records changed.")
