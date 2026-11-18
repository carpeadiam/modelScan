"""Evaluation on the chronological hold-out set; compares 4 strategies."""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score)

from ml.preprocess import (MODEL_NAMES, chronological_split, get_features, load_dataset, make_target,
                           sufficiency, validate_dataset)
from pg.config import ROOT, get_settings
from pg.features import FEATURE_COLUMNS, rule_based_probability
from pg.storage import get_storage

THRESHOLD = 0.5  # classification threshold used for accuracy/precision/recall (positive class = failure)


def metrics_for(y_true, y_prob, threshold=THRESHOLD) -> dict:
    y_true = np.asarray(y_true)
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    both = len(set(y_true.tolist())) == 2
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if both else None,
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else None,
        "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) else None,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n_test": int(len(y_true)),
    }


def run_evaluation(df, storage, test_fraction=0.3, allow_test_data=False, write=True, figures=False) -> dict:
    df = validate_dataset(df, allow_test_data)
    train_df, test_df = chronological_split(df, test_fraction)
    y_tr, y_te = make_target(train_df), make_target(test_df)
    suff = sufficiency(y_tr, y_te)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "threshold": THRESHOLD,
              "dataset": {"rows": len(df), "class_distribution": {
                  "success": int((make_target(df) == 0).sum()), "failure": int((make_target(df) == 1).sum())},
                  "train_rows": len(train_df), "test_rows": len(test_df),
                  "train_period": [train_df["timestamp"].min(), train_df["timestamp"].max()],
                  "test_period": [test_df["timestamp"].min(), test_df["timestamp"].max()],
                  "failure_types": df["failure_type"].value_counts().to_dict()},
              "sufficiency": suff, "models": {}, "baselines": {}, "selected_model": None}
    if len(test_df) == 0:
        result["status"] = "insufficient_data"
    else:
        X_te = get_features(test_df)
        result["baselines"]["no_prediction"] = metrics_for(y_te, np.zeros(len(y_te)))
        result["baselines"]["rule_based"] = metrics_for(
            y_te, [rule_based_probability(r) for r in X_te.to_dict("records")])
        for name in MODEL_NAMES:
            try:
                model = joblib.load(io.BytesIO(storage.read_bytes(f"models/{name}.joblib")))
            except FileNotFoundError:
                continue
            result["models"][name] = metrics_for(y_te, model.predict_proba(X_te)[:, 1])
        result["status"] = "ok" if result["models"] else "no_trained_models"
        scored = {n: m for n, m in result["models"].items()}
        if scored:
            result["selected_model"] = max(scored, key=lambda n: ((scored[n]["roc_auc"] or 0), scored[n]["f1"]))
        if not suff["statistically_meaningful"]:
            result["caution"] = ("NOT statistically meaningful: " + "; ".join(suff["warnings"] or ["cannot fit"]) +
                                 ". Do not draw conclusions from these numbers.")
    if write:
        storage.write_json("reports/model_metrics.json", result)
        meta = storage.read_json_or_none("models/metadata.json")
        if meta is not None:
            meta["selected_model"] = result["selected_model"]
            meta["statistically_meaningful"] = suff["statistically_meaningful"]
            storage.write_json("models/metadata.json", meta)
    if figures and result["models"]:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        items = list(result["models"].items())
        fig, axes = plt.subplots(1, len(items), figsize=(4 * len(items), 3.5))
        for ax, (n, m) in zip(np.atleast_1d(axes), items):
            cm = m["confusion_matrix"]
            ax.imshow([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]], cmap="Blues")
            for (i, j), v in np.ndenumerate([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]]):
                ax.text(j, i, v, ha="center", va="center")
            ax.set_xticks([0, 1], ["pred success", "pred failure"]); ax.set_yticks([0, 1], ["success", "failure"])
            ax.set_title(n)
        (ROOT / "reports" / "figures").mkdir(parents=True, exist_ok=True)
        fig.tight_layout(); fig.savefig(ROOT / "reports" / "figures" / "confusion_matrices.png", dpi=120)
    return result


def print_report(r: dict):
    print(f"status: {r['status']}")
    print("class distribution:", r["dataset"]["class_distribution"], "| train/test rows:",
          r["dataset"]["train_rows"], r["dataset"]["test_rows"])
    if "caution" in r:
        print("\n!!", r["caution"], "\n")
    rows = {**r["baselines"], **r["models"]}
    print(f"{'strategy':22} acc    prec   rec    f1     auc    FPR    FNR    (tn fp fn tp)")
    f = lambda v: "  n/a " if v is None else f"{v:6.3f}"  # noqa: E731
    for n, m in rows.items():
        c = m["confusion_matrix"]
        print(f"{n:22}{f(m['accuracy'])}{f(m['precision'])}{f(m['recall'])}{f(m['f1'])}{f(m['roc_auc'])}"
              f"{f(m['false_positive_rate'])}{f(m['false_negative_rate'])}  ({c['tn']} {c['fp']} {c['fn']} {c['tp']})")
    print("selected model:", r["selected_model"])


if __name__ == "__main__":
    storage = get_storage(get_settings())
    data = load_dataset(storage)
    if data is None:
        sys.exit("No dataset found. Run scripts/run_experiment.py then scripts/aggregate_dataset.py first.")
    res = run_evaluation(data, storage, figures=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "model_metrics.json").write_text(json.dumps(res, indent=2))
    print_report(res)
