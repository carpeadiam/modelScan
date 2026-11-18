import pandas as pd
from .features import FEATURES

REQUIRED = ['cloudflare_build_uuid', 'commit_sha', 'timestamp', 'actual_build_outcome', 'actual_duration']

def validate_records(records):
    seen = set(); valid = []; rejected = []
    for row in records:
        reason = None
        if any(row.get(k) in (None, '') for k in REQUIRED): reason = 'missing_required_field'
        elif row.get('collection_status') != 'verified': reason = 'not_verified'
        elif row.get('actual_build_outcome') not in ('success', 'failure'): reason = 'not_binary_pipeline_outcome'
        elif row.get('cloudflare_build_uuid') in seen: reason = 'duplicate_build_uuid'
        if reason: rejected.append({'record': row, 'reason': reason})
        else:
            seen.add(row['cloudflare_build_uuid']); valid.append(row)
    return valid, rejected

def records_to_frame(records):
    valid, _ = validate_records(records)
    rows = []
    for r in valid:
        row = {k: (r.get('features') or {}).get(k) for k in FEATURES}
        row.update({k: r.get(k) for k in REQUIRED})
        row['label'] = int(r['actual_build_outcome'] == 'failure')
        rows.append(row)
    return pd.DataFrame(rows)
