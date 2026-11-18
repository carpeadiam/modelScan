#!/usr/bin/env python3
"""Aggregate verified raw execution records into dataset/real_pipeline_history.csv (+ storage copy)."""
import _bootstrap  # noqa: F401
import json
from datetime import datetime, timezone
from hashlib import sha256

from pg.config import ROOT, get_settings
from pg.dataset import build_dataset, summarize_exclusions
from pg.records import load_records
from pg.storage import get_storage

DATASET_KEY = "datasets/real_pipeline_history.csv"
MANIFEST_KEY = "datasets/manifest.json"


def aggregate(storage, local_dir=ROOT / "dataset"):
    records = load_records(storage)
    df, excl = build_dataset(records)
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "raw_records": len(records),
                "verified_rows": len(df), "excluded": len(excl), "exclusion_reasons": summarize_exclusions(excl),
                "exclusions": excl}
    storage.write_json("datasets/exclusions.json", excl)
    if df.empty:
        manifest["note"] = "No verified executions. Collect real executions first (scripts/run_experiment.py)."
        storage.write_json(MANIFEST_KEY, manifest)
        return df, manifest
    csv_bytes = df.to_csv(index=False).encode()
    manifest["sha256"] = sha256(csv_bytes).hexdigest()
    storage.write_bytes(DATASET_KEY, csv_bytes, "text/csv")
    storage.write_json(MANIFEST_KEY, manifest)
    local_dir.mkdir(exist_ok=True)
    (local_dir / "real_pipeline_history.csv").write_bytes(csv_bytes)
    return df, manifest


if __name__ == "__main__":
    df, m = aggregate(get_storage(get_settings()))
    print(json.dumps({k: v for k, v in m.items() if k != "exclusions"}, indent=2))
    if df.empty:
        print("\nNo dataset written: there are no verified real executions yet.")
    else:
        print(f"\nWrote dataset/real_pipeline_history.csv ({len(df)} rows)")
        print(df["pipeline_status"].value_counts().to_string())
