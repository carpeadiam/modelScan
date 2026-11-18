"""Predict failure probability from PRE-BUILD features only. Used by Flask and by Cloud Build stage 4."""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import pandas as pd

from pg.features import FEATURE_COLUMNS, FORBIDDEN_COLUMNS, assert_no_leakage, risk_category


class Artifacts:
    def __init__(self, reader):
        self.reader = reader  # reader(relative_name) -> bytes
        self.metadata = json.loads(reader("metadata.json").decode())
        self._cache = {}

    def model(self, name):
        if name not in self._cache:
            self._cache[name] = joblib.load(io.BytesIO(self.reader(f"{name}.joblib")))
        return self._cache[name]

    @classmethod
    def from_dir(cls, path):
        return cls(lambda n: (Path(path) / n).read_bytes())

    @classmethod
    def from_storage(cls, storage):
        return cls(lambda n: storage.read_bytes(f"models/{n}"))


def clean_features(features: dict) -> dict:
    leaked = sorted(set(features) & set(FORBIDDEN_COLUMNS))
    if leaked:
        raise ValueError(f"Feature leakage: post-execution fields are not accepted as inputs: {leaked}")
    unknown = sorted(set(features) - set(FEATURE_COLUMNS))
    if unknown:
        raise ValueError(f"Unknown feature(s): {unknown}")
    out = {}
    for c in FEATURE_COLUMNS:
        v = features.get(c)
        out[c] = None if v in (None, "") else float(v)
    return out


def predict(features: dict, artifacts: Artifacts, model_name: str | None = None,
            low: float = 0.40, high: float = 0.70) -> dict:
    feats = clean_features(features)
    assert_no_leakage(list(feats))
    name = model_name or artifacts.metadata.get("selected_model") or "random_forest"
    row = pd.DataFrame([feats], columns=FEATURE_COLUMNS).astype(float)
    p = float(artifacts.model(name).predict_proba(row)[0, 1])
    validated = bool(artifacts.metadata.get("statistically_meaningful"))
    return {
        "status": "ok", "failure_probability": p, "risk_category": risk_category(p, low, high),
        "model_used": name, "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
        "features_used": feats, "missing_features": [k for k, v in feats.items() if v is None],
        "model_validated": validated,
        "warning": None if validated else "Model was trained on insufficient data; prediction is NOT validated "
                                           "and is advisory only.",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--features-file", required=True)
    ap.add_argument("--out")
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    payload = json.load(open(a.features_file))
    report = predict(payload.get("features", payload), Artifacts.from_dir(a.model_dir), a.model)
    text = json.dumps(report, indent=2)
    Path(a.out).write_text(text) if a.out else print(text)
