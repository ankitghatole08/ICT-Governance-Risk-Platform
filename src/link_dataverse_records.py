"""Connect synthetic CSV business IDs to Dataverse lookup records.
Install: pip install requests msal
Run: python -m src.link_dataverse_records
Keep APPLY_CHANGES=False until the entire dry run succeeds.
"""
import csv
from pathlib import Path
from urllib.parse import quote

import msal
import requests

BASE = 'https://org565debe8.crm4.dynamics.com'
API = BASE + '/api/data/v9.2'
ROOT = Path(__file__).resolve().parents[1]
CLIENT_ID = '51f81489-12ee-4a9e-aaae-a2591f45987d'
APPLY_CHANGES = True


def create_session():
    app = msal.PublicClientApplication(CLIENT_ID, authority='https://login.microsoftonline.com/organizations')
    result = app.acquire_token_interactive(scopes=[BASE + '/user_impersonation'], port=8400)
    if 'access_token' not in result:
        raise RuntimeError('Authentication failed: ' + str(result.get('error_description', result.get('error'))))
    session = requests.Session()
    session.headers.update({'Authorization': 'Bearer ' + result['access_token'],
                            'Accept': 'application/json', 'OData-Version': '4.0',
                            'OData-MaxVersion': '4.0', 'Content-Type': 'application/json'})
    return session


def request(session, method, url, **kwargs):
    response = session.request(method, url, timeout=60, **kwargs)
    if not response.ok:
        raise RuntimeError(f'{method} failed ({response.status_code}): {response.text[:800]}')
    return response.json() if response.content else None


def entity(session, name):
    return request(session, 'GET', f"{API}/EntityDefinitions(LogicalName='{name}')"
                   '?$select=LogicalName,EntitySetName,PrimaryIdAttribute')


def relation(session, source, lookup):
    url = (f"{API}/EntityDefinitions(LogicalName='{source}')/ManyToOneRelationships"
           '?$select=ReferencingAttribute,ReferencedEntity,ReferencingEntityNavigationPropertyName')
    found = []
    while url:
        data = request(session, 'GET', url)
        found.extend(x for x in data['value'] if x['ReferencingAttribute'].lower() == lookup.lower())
        url = data.get('@odata.nextLink')
    if len(found) != 1:
        raise RuntimeError(f'Expected exactly one lookup relationship {source}.{lookup}; found {len(found)}')
    return found[0]


def business_column(session, table, display_name):
    url = (f"{API}/EntityDefinitions(LogicalName='{table}')/Attributes"
           '?$select=LogicalName,DisplayName,AttributeType')
    matches = []
    while url:
        data = request(session, 'GET', url)
        for attr in data['value']:
            labels = attr.get('DisplayName', {}).get('LocalizedLabels') or []
            if any(label.get('Label', '').casefold() == display_name.casefold() for label in labels):
                matches.append(attr)
        url = data.get('@odata.nextLink')
    if len(matches) != 1:
        raise RuntimeError(f'Expected one column called {display_name!r} in {table}, found {len(matches)}')
    if matches[0].get('AttributeType') not in ('String', 'Memo'):
        raise RuntimeError(f'{display_name} is not a text column')
    return matches[0]['LogicalName']


def rows(session, entity_meta, fields):
    url = f"{API}/{entity_meta['EntitySetName']}?$select={','.join(fields)}"
    all_rows = []
    while url:
        data = request(session, 'GET', url)
        all_rows.extend(data['value'])
        url = data.get('@odata.nextLink')
    return all_rows


def index(rows, key_field, guid_field):
    result = {}
    for row in rows:
        key = str(row.get(key_field) or '').strip()
        if not key:
            continue
        if key in result:
            raise RuntimeError(f'Duplicate Dataverse business ID: {key}')
        result[key] = row[guid_field]
    return result


def csv_rows(filename):
    with (ROOT / 'data' / 'raw' / filename).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def plan(session, source, lookup, source_label, target_label, csv_name, csv_source, csv_target):
    rel = relation(session, source, lookup)
    target = rel['ReferencedEntity']  # Discover real target table name from Dataverse
    source_meta, target_meta = entity(session, source), entity(session, target)
    source_col = business_column(session, source, source_label)
    target_col = business_column(session, target, target_label)
    source_records = rows(session, source_meta, [source_meta['PrimaryIdAttribute'], source_col])
    target_records = rows(session, target_meta, [target_meta['PrimaryIdAttribute'], target_col])
    source_index = index(source_records, source_col, source_meta['PrimaryIdAttribute'])
    target_index = index(target_records, target_col, target_meta['PrimaryIdAttribute'])
    matches, missing, seen = [], [], set()
    for row in csv_rows(csv_name):
        sid, tid = row[csv_source].strip(), row[csv_target].strip()
        if sid in seen:
            raise RuntimeError(f'Duplicate CSV source business ID {sid} in {csv_name}')
        seen.add(sid)
        if sid not in source_index or tid not in target_index:
            missing.append((sid, tid))
        else:
            matches.append((source_index[sid], target_index[tid]))
    print(f'\n{source} -> {target} ({lookup})')
    print(f'Business ID columns: {source_col} -> {target_col}')
    print(f'Dataverse records: {len(source_records)} source, {len(target_records)} target')
    print(f'Matched: {len(matches)}; missing: {len(missing)}')
    if missing:
        print('Missing examples:', missing[:5])
        raise RuntimeError('Missing matches; no changes made')
    return source_meta, target_meta, rel['ReferencingEntityNavigationPropertyName'], matches


def main():
    session = create_session()
    configurations = [
        ('ict_securityfinding', 'ict_asset', 'Finding Business ID', 'Asset Business ID',
         'security_findings.csv', 'finding_id', 'asset_id'),
        ('ict_securityfinding', 'ict_ictcontrol', 'Finding Business ID', 'Control Business ID',
         'security_findings.csv', 'finding_id', 'control_id'),
        ('ict_remediationaction', 'ict_securityfinding', 'Action Business ID', 'Finding Business ID',
         'remediation_actions.csv', 'action_id', 'finding_id'),
    ]
    plans = [plan(session, *cfg) for cfg in configurations]
    print('\nAll three relationship checks passed.')
    if not APPLY_CHANGES:
        print('DRY RUN: No records changed. Set APPLY_CHANGES=True only after reviewing the output.')
        return
    for src, dst, nav, links in plans:
        for src_guid, dst_guid in links:
            url = f"{API}/{src['EntitySetName']}({src_guid})"
            payload = {f'{nav}@odata.bind': f"/{dst['EntitySetName']}({dst_guid})"}
            request(session, 'PATCH', url, json=payload)
        print(f"Updated {len(links)}: {src['LogicalName']} -> {dst['LogicalName']}")
    print('SUCCESS: All relationships linked.')


if __name__ == '__main__':
    main()
