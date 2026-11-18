#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
p = Path(__file__).resolve().parents[1] / 'dataset' / 'real_pipeline_history.csv'
if not p.exists():
    print('No dataset exists yet. This is expected before real builds complete.'); raise SystemExit(0)
df = pd.read_csv(p)
print(f'Rows: {len(df)} | duplicate UUIDs: {df.cloudflare_build_uuid.duplicated().sum()} | missing cells: {int(df.isna().sum().sum())}')
print('Labels:', df.label.value_counts(dropna=False).to_dict())
if df.cloudflare_build_uuid.duplicated().any() or df.label.isna().any(): raise SystemExit('Dataset validation failed')
