"""Train Logistic Regression and Random Forest on the REAL aggregated dataset (chronological split)."""
from __future__ import annotations

import io
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import sklearn

from ml.evaluate import print_report, run_evaluation
from ml.preprocess import (MODEL_NAMES, build_model, chronological_split, get_features, load_dataset,
                           make_target, sufficiency, validate_dataset)
from pg.config import ROOT, get_settings
from pg.features import FEATURE_COLUMNS
from pg.storage import get_storage


def train(df, storage, test_fraction=0.3, allow_test_data=False, figures=False) -> dict:
    df = validate_dataset(df, allow_test_data)
    train_df, test_df = chronological_split(df, test_fraction)
    y_tr, y_te = make_target(train_df), make_target(test_df)
    suff = sufficiency(y_tr, y_te)
    if not suff["can_fit"]:
        res = run_evaluation(df, storage, test_fraction, allow_test_data, figures=False)
        res["status"] = "insufficient_data"
        res["caution"] = ("Training skipped: the chronological training split lacks examples of one class "
                          f"({suff['train_class_counts']}). Collect more real executions of both outcomes.")
        storage.write_json("reports/model_metrics.json", res)
        return res
    X_tr = get_features(train_df)
    for name in MODEL_NAMES:
        model = build_model(name).fit(X_tr, y_tr)
        buf = io.BytesIO(); joblib.dump(model, buf)
        storage.write_bytes(f"models/{name}.joblib", buf.getvalue())
    storage.write_json("models/metadata.json", {
        "trained_at": datetime.now(timezone.utc).isoformat(), "feature_columns": FEATURE_COLUMNS,
        "train_rows": len(train_df), "test_rows": len(test_df), "test_fraction": test_fraction,
        "train_last_timestamp": str(train_df["timestamp"].max()), "sklearn_version": sklearn.__version__,
        "execution_ids_sha": __import__("hashlib").sha256(",".join(sorted(df["execution_id"])).encode()).hexdigest(),
        "statistically_meaningful": suff["statistically_meaningful"], "selected_model": None,
        "class_distribution_train": suff["train_class_counts"],
    })
    return run_evaluation(df, storage, test_fraction, allow_test_data, figures=figures)


if __name__ == "__main__":
    storage = get_storage(get_settings())
    data = load_dataset(storage)
    if data is None:
        sys.exit("No dataset found. Collect real executions first (scripts/run_experiment.py), then "
                 "python scripts/aggregate_dataset.py. Nothing was trained.")
    result = train(data, storage, figures=True)
    import json
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "model_metrics.json").write_text(json.dumps(result, indent=2))
    print_report(result) if result.get("models") else print(result.get("caution", result["status"]))
