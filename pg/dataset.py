"""Build the training dataset from VERIFIED raw execution records (chronological, leak-free history)."""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import List, Tuple

import pandas as pd

from .buildapi import parse_ts
from .features import DATASET_COLUMNS, FEATURE_COLUMNS
from .provenance import DATA_SOURCE, verify_record
from .scenarios import classify_failure

GIT_FEATURES = ["files_changed", "lines_added", "lines_deleted", "python_files_changed",
                "test_files_changed", "dependency_changes", "known_test_count"]


def history_features(prior: List[dict]) -> dict:
    """prior: parsed records that FINISHED before the current execution was created, sorted by finish time."""
    if not prior:
        return {"previous_build_failed": None, "previous_3_build_failures": 0,
                "historical_avg_duration": None, "historical_failure_rate": None}
    fails = [p["status"] == "FAILURE" for p in prior]
    durs = [p["duration_seconds"] for p in prior if p["duration_seconds"] is not None]
    return {
        "previous_build_failed": int(fails[-1]),
        "previous_3_build_failures": int(sum(fails[-3:])),
        "historical_avg_duration": mean(durs) if durs else None,
        "historical_failure_rate": sum(fails) / len(fails),
    }


def build_dataset(records: List[dict]) -> Tuple[pd.DataFrame, List[dict]]:
    """Returns (dataframe, exclusions). Every exclusion is reported with a reason; nothing is imputed."""
    exclusions: List[dict] = []
    seen, verified = set(), []
    for rec in records:
        ok, reasons = verify_record(rec)
        eid = rec.get("execution_id") if isinstance(rec, dict) else None
        if ok and eid in seen:
            exclusions.append({"execution_id": eid, "reasons": ["duplicate_execution_id"]})
            continue
        if not ok:
            exclusions.append({"execution_id": eid, "reasons": reasons})
            continue
        parsed, meta = rec["parsed"], rec.get("pipelineguard") or {}
        if parsed["failed_step"] == "risk-gate":
            exclusions.append({"execution_id": eid, "reasons": ["blocked_by_prediction_gate (label contaminated by the model)"]})
            continue
        feats = meta.get("submitted_features") or {}
        missing = [c for c in GIT_FEATURES if feats.get(c) is None]
        if missing:
            exclusions.append({"execution_id": eid, "reasons": [f"missing_pre_build_git_metrics:{','.join(missing)}"]})
            continue
        seen.add(eid)
        verified.append(rec)

    verified.sort(key=lambda r: (r["parsed"]["create_time"], r["execution_id"]))
    parsed_list = [r["parsed"] for r in verified]
    rows = []
    for rec in verified:
        p, meta = rec["parsed"], rec["pipelineguard"]
        created = parse_ts(p["create_time"])
        prior = sorted((q for q in parsed_list if q["execution_id"] != p["execution_id"]
                        and q["finish_time"] and parse_ts(q["finish_time"]) <= created),
                       key=lambda q: q["finish_time"])
        hist = history_features(prior)
        feats = meta["submitted_features"]
        scenario = meta.get("injected_scenario")
        rows.append({
            "execution_id": p["execution_id"],
            "experiment_id": meta.get("experiment_id"),
            "timestamp": p["create_time"],
            "commit_sha": p["commit_sha"] or meta.get("commit_sha"),
            **{c: feats.get(c) for c in GIT_FEATURES},
            **hist,
            "build_duration": p["duration_seconds"],
            "pipeline_status": "success" if p["status"] == "SUCCESS" else "failure",
            "failure_type": classify_failure(p["status"], scenario, p["failed_step"]),
            "injected_scenario": scenario or "none",
            "failed_step": p["failed_step"],
            "data_source": DATA_SOURCE,
        })
    df = pd.DataFrame(rows, columns=DATASET_COLUMNS)
    return df, exclusions


def summarize_exclusions(exclusions: List[dict]) -> dict:
    return dict(Counter(r for e in exclusions for r in e["reasons"]))
