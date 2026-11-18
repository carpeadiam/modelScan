"""Read-only data access for the dashboard. Everything comes from collected real records."""
from __future__ import annotations

import io

import pandas as pd

from .storage import Storage

DATASET_KEY = "datasets/real_pipeline_history.csv"


def load_df(storage: Storage):
    try:
        return pd.read_csv(io.BytesIO(storage.read_bytes(DATASET_KEY)))
    except FileNotFoundError:
        return None


def overview(df) -> dict:
    if df is None or df.empty:
        return {"empty": True}
    fails = df[df["pipeline_status"] == "failure"]
    last = df.sort_values("timestamp").iloc[-1]
    return {"empty": False, "total": len(df), "successful": int((df["pipeline_status"] == "success").sum()),
            "failed": len(fails), "failure_rate": len(fails) / len(df),
            "controlled_failures": int(fails["failure_type"].astype(str).str.startswith("injected").sum()),
            "natural_failures": int((fails["failure_type"] == "natural").sum()),
            "last_execution": {"execution_id": last["execution_id"], "timestamp": last["timestamp"],
                               "status": last["pipeline_status"]}}


def history(df, limit=500) -> list:
    if df is None or df.empty:
        return []
    cols = ["execution_id", "timestamp", "commit_sha", "pipeline_status", "build_duration", "failure_type", "experiment_id"]
    out = df.sort_values("timestamp", ascending=False).head(limit)[cols]
    return out.astype(object).where(out.notna(), None).to_dict("records")


def experiments(storage: Storage) -> list:
    out = []
    for key in storage.list_keys("experiments/"):
        if key.endswith("/progress.json"):
            d = storage.read_json(key)
            runs = d["runs"]
            done = [r for r in runs if r["state"] == "collected"]
            out.append({"experiment_id": d["experiment_id"], "requested": d["requested"], "completed": len(done),
                        "successful": sum(r["build_status"] == "SUCCESS" for r in done),
                        "failed": sum(r["build_status"] == "FAILURE" for r in done),
                        "progress_pct": round(100 * len(done) / max(1, len(runs)), 1),
                        "updated_at": d.get("updated_at")})
    return sorted(out, key=lambda e: e["experiment_id"], reverse=True)
