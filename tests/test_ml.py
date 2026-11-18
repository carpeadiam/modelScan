import numpy as np
import pandas as pd
import pytest

from conftest import fake_build
from ml.evaluate import metrics_for, run_evaluation
from ml.predict import Artifacts, predict
from ml.preprocess import chronological_split, get_features, sufficiency, make_target
from ml.train import train
from pg.dataset import build_dataset
from pg.features import FEATURE_COLUMNS
from pg.records import make_record


def mock_df(mock_records):
    df, _ = build_dataset(mock_records)
    df["data_source"] = "unit_test_mock"      # mock rows are allowed ONLY via allow_test_data in tests
    return df


def test_chronological_split_has_no_overlap(mock_records):
    df = mock_df(mock_records)
    tr, te = chronological_split(df.sample(frac=1, random_state=1), 0.25)
    assert pd.to_datetime(tr["timestamp"]).max() <= pd.to_datetime(te["timestamp"]).min()
    assert len(tr) + len(te) == len(df)


def test_features_exclude_labels(mock_records):
    X = get_features(mock_df(mock_records))
    assert list(X.columns) == FEATURE_COLUMNS


def test_train_predict_roundtrip(storage, mock_records):
    res = train(mock_df(mock_records), storage, allow_test_data=True)
    assert res["status"] == "ok" and set(res["models"]) == {"logistic_regression", "random_forest"}
    m = res["models"]["random_forest"]
    assert set(m) >= {"accuracy", "precision", "recall", "f1", "roc_auc", "false_positive_rate", "false_negative_rate"}
    arts = Artifacts.from_storage(storage)
    out = predict({"files_changed": 3, "lines_added": 20}, arts, "logistic_regression")
    assert 0 <= out["failure_probability"] <= 1 and out["risk_category"] in {"LOW", "MEDIUM", "HIGH"}
    assert out["model_used"] == "logistic_regression" and "files_changed" in out["features_used"]
    assert "historical_avg_duration" in out["missing_features"]


def test_predict_rejects_leaky_inputs(storage, mock_records):
    train(mock_df(mock_records), storage, allow_test_data=True)
    arts = Artifacts.from_storage(storage)
    for bad in ({"build_duration": 5}, {"pipeline_status": "failure"}, {"failure_type": "x"}, {"nope": 1}):
        with pytest.raises(ValueError):
            predict(bad, arts)


def test_single_class_data_is_not_trained(storage):
    recs = [make_record(fake_build(i), "p") for i in range(10)]
    df, _ = build_dataset(recs); df["data_source"] = "unit_test_mock"
    res = train(df, storage, allow_test_data=True)
    assert res["status"] == "insufficient_data" and "Training skipped" in res["caution"]
    assert not storage.exists("models/random_forest.joblib")


def test_small_dataset_flagged_not_meaningful(storage, mock_records):
    res = train(mock_df(mock_records[:12]), storage, allow_test_data=True)
    assert not res["sufficiency"]["statistically_meaningful"]
    assert "NOT statistically meaningful" in res.get("caution", "")


def test_metrics_edge_cases():
    m = metrics_for([0, 0, 1, 1], [0.1, 0.6, 0.4, 0.9])
    assert m["confusion_matrix"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 1} and m["roc_auc"] == 0.75
    assert metrics_for([0, 0], [0.1, 0.2])["roc_auc"] is None


def test_sufficiency_counts():
    s = sufficiency(pd.Series([0, 0, 0]), pd.Series([0]))
    assert not s["can_fit"] and not s["statistically_meaningful"]
