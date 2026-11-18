"""Dataset loading/validation, leakage-safe feature selection, chronological split, model factories."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pg.features import DATASET_COLUMNS, FEATURE_COLUMNS, assert_no_leakage
from pg.provenance import DATA_SOURCE

DATASET_KEY = "datasets/real_pipeline_history.csv"
LOCAL_DATASET = Path(__file__).resolve().parent.parent / "dataset" / "real_pipeline_history.csv"
MIN_TOTAL, MIN_PER_CLASS_TRAIN, MIN_PER_CLASS_TEST = 30, 5, 3
MODEL_NAMES = ("logistic_regression", "random_forest")


def load_dataset(storage=None, local_path: Path = LOCAL_DATASET):
    """Return the aggregated real dataset or None if it does not exist yet."""
    if storage is not None:
        try:
            return pd.read_csv(io.BytesIO(storage.read_bytes(DATASET_KEY)))
        except FileNotFoundError:
            pass
    if local_path.exists():
        return pd.read_csv(local_path)
    return None


def validate_dataset(df: pd.DataFrame, allow_test_data: bool = False) -> pd.DataFrame:
    """Provenance + schema checks. `allow_test_data` exists ONLY for unit tests; CLIs never set it."""
    missing = [c for c in DATASET_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    if df["execution_id"].isna().any() or (df["execution_id"].astype(str).str.strip() == "").any():
        raise ValueError("Provenance violation: rows without execution_id")
    df = df.drop_duplicates(subset="execution_id", keep="first").copy()
    allowed = {DATA_SOURCE} | ({"unit_test_mock"} if allow_test_data else set())
    bad = set(df["data_source"].unique()) - allowed
    if bad:
        raise ValueError(f"Provenance violation: data_source values {sorted(bad)} are not '{DATA_SOURCE}'")
    if not set(df["pipeline_status"].unique()) <= {"success", "failure"}:
        raise ValueError("pipeline_status must be 'success' or 'failure'")
    return df


def make_target(df: pd.DataFrame) -> pd.Series:
    return (df["pipeline_status"] == "failure").astype(int)


def get_features(df: pd.DataFrame) -> pd.DataFrame:
    assert_no_leakage(FEATURE_COLUMNS)
    return df[FEATURE_COLUMNS].apply(pd.to_numeric, errors="raise").astype(float)


def chronological_split(df: pd.DataFrame, test_fraction: float = 0.3):
    ordered = df.assign(_ts=pd.to_datetime(df["timestamp"], utc=True)).sort_values(["_ts", "execution_id"])
    cut = int(round(len(ordered) * (1 - test_fraction)))
    cut = min(max(cut, 1), len(ordered) - 1) if len(ordered) > 1 else len(ordered)
    return ordered.iloc[:cut].drop(columns="_ts"), ordered.iloc[cut:].drop(columns="_ts")


def sufficiency(y_train, y_test) -> dict:
    total = len(y_train) + len(y_test)
    ctr = {int(c): int((y_train == c).sum()) for c in (0, 1)}
    cte = {int(c): int((y_test == c).sum()) for c in (0, 1)}
    warnings = []
    if total < MIN_TOTAL:
        warnings.append(f"only {total} observations (< {MIN_TOTAL})")
    if min(ctr.values()) < MIN_PER_CLASS_TRAIN:
        warnings.append(f"training set has fewer than {MIN_PER_CLASS_TRAIN} examples of a class: {ctr}")
    if min(cte.values()) < MIN_PER_CLASS_TEST:
        warnings.append(f"test set has fewer than {MIN_PER_CLASS_TEST} examples of a class: {cte}")
    can_fit = min(ctr.values()) > 0
    return {"total": total, "train_class_counts": {"success": ctr[0], "failure": ctr[1]},
            "test_class_counts": {"success": cte[0], "failure": cte[1]}, "can_fit": can_fit,
            "statistically_meaningful": can_fit and not warnings, "warnings": warnings}


def build_model(name: str) -> Pipeline:
    imp = lambda: SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)  # noqa: E731
    if name == "logistic_regression":
        pre = ColumnTransformer([("num", Pipeline([("imp", imp()), ("sc", StandardScaler())]), FEATURE_COLUMNS)])
        clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    elif name == "random_forest":
        pre = ColumnTransformer([("num", Pipeline([("imp", imp())]), FEATURE_COLUMNS)])
        clf = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, class_weight="balanced_subsample",
                                     random_state=42)
    else:
        raise ValueError(name)
    return Pipeline([("pre", pre), ("clf", clf)])
