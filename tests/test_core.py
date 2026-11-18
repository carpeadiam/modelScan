import json

import pandas as pd
import pytest

from conftest import fake_build
from ml.preprocess import validate_dataset
from pg.buildapi import extract_meta, parse_build, parse_ts
from pg.dataset import build_dataset, history_features
from pg.features import DATASET_COLUMNS, FEATURE_COLUMNS, assert_no_leakage, risk_category
from pg.provenance import verify_record
from pg.records import make_record, save_record, load_records
from pg.scenarios import classify_failure, plan_scenarios, DEFAULT_WEIGHTS


def test_parse_ts_nanoseconds_and_none():
    assert parse_ts("2026-01-01T00:00:00.123456789Z").microsecond == 123456
    assert parse_ts(None) is None


def test_parse_build_fields():
    p = parse_build(fake_build(1, "FAILURE", failed_step="build"))
    assert p["status"] == "FAILURE" and p["failed_step"] == "build"
    assert p["duration_seconds"] == 60 and p["region"] == "global" and p["commit_sha"] == "sha1"


def test_missing_start_time_stays_none():
    b = fake_build(1); del b["startTime"]
    assert parse_build(b)["duration_seconds"] is None


def test_extract_meta():
    m = extract_meta(fake_build(2, scenario="build_failure"))
    assert m["injected_scenario"] == "build_failure" and m["submitted_features"]["files_changed"] == 3
    assert m["submitted_features"]["historical_avg_duration"] is None


def test_provenance_accepts_and_rejects():
    rec = make_record(fake_build(1), "p")
    assert verify_record(rec) == (True, [])
    bad = json.loads(json.dumps(rec)); bad["verification"]["verified"] = False
    assert "not_verified_via_cloud_build_api" in verify_record(bad)[1]
    bad = json.loads(json.dumps(rec)); bad["build"]["id"] = "other"
    assert "execution_id_mismatch_with_api_payload" in verify_record(bad)[1]
    working = make_record(fake_build(2, "WORKING"), "p")
    assert any(r.startswith("incomplete_execution") for r in verify_record(working)[1])
    timeout = make_record(fake_build(3, "TIMEOUT"), "p")
    assert any("non_labelled" in r for r in verify_record(timeout)[1])
    assert not verify_record({"execution_id": "x"})[0]


def test_aggregation_duplicates_and_exclusions(mock_records):
    recs = mock_records + [mock_records[0], make_record(fake_build(99, "WORKING"), "p")]
    df, excl = build_dataset(recs)
    assert df["execution_id"].is_unique and len(df) == len(mock_records)
    reasons = {r for e in excl for r in e["reasons"]}
    assert "duplicate_execution_id" in reasons and any(r.startswith("incomplete") for r in reasons)
    assert list(df.columns) == DATASET_COLUMNS


def test_missing_git_metrics_excluded():
    b = fake_build(1); del b["substitutions"]["_FILES_CHANGED"]
    df, excl = build_dataset([make_record(b, "p")])
    assert df.empty and "missing_pre_build_git_metrics" in excl[0]["reasons"][0]


def test_history_uses_only_prior_finished_builds(mock_records):
    df, _ = build_dataset(mock_records)
    first = df.iloc[0]
    assert pd.isna(first["previous_build_failed"]) and pd.isna(first["historical_avg_duration"])
    # row 1 can only see row 0 (finished 62s after its creation, 10 min before row 1's creation)
    assert df.iloc[1]["previous_build_failed"] == (df.iloc[0]["pipeline_status"] == "failure")
    assert df.iloc[1]["historical_failure_rate"] == (1.0 if df.iloc[0]["pipeline_status"] == "failure" else 0.0)


def test_history_features_function():
    prior = [{"status": "FAILURE", "duration_seconds": 10}, {"status": "SUCCESS", "duration_seconds": 30},
             {"status": "FAILURE", "duration_seconds": None}, {"status": "FAILURE", "duration_seconds": 20}]
    h = history_features(prior)
    assert h["previous_3_build_failures"] == 2 and h["previous_build_failed"] == 1
    assert h["historical_avg_duration"] == 20 and h["historical_failure_rate"] == 0.75


def test_failure_classification():
    assert classify_failure("SUCCESS", "success", None) == "none"
    assert classify_failure("FAILURE", "unit_test_failure", "unit-tests") == "injected:unit_test_failure"
    assert classify_failure("FAILURE", "unit_test_failure", "build") == "natural"
    assert classify_failure("FAILURE", "success", "unit-tests") == "natural"
    assert classify_failure("FAILURE", "success", "risk-gate") == "blocked_by_prediction_gate"


def test_blocked_by_gate_excluded():
    b = fake_build(1, "FAILURE", failed_step="risk-gate")
    df, excl = build_dataset([make_record(b, "p")])
    assert df.empty and "blocked_by_prediction_gate" in excl[0]["reasons"][0]


def test_scenario_plan_is_deterministic_and_complete():
    a = plan_scenarios(20, DEFAULT_WEIGHTS, "s"); b = plan_scenarios(20, DEFAULT_WEIGHTS, "s")
    assert a == b and len(a) == 20 and a.count("success") == 10


def test_leakage_guard():
    assert_no_leakage(FEATURE_COLUMNS)
    for bad in ("build_duration", "pipeline_status", "failure_type", "injected_scenario"):
        with pytest.raises(ValueError):
            assert_no_leakage(FEATURE_COLUMNS + [bad])
    assert not {"build_duration", "pipeline_status", "failure_type", "injected_scenario", "failed_step"} & set(FEATURE_COLUMNS)


def test_risk_categories():
    assert risk_category(0.39) == "LOW" and risk_category(0.40) == "MEDIUM"
    assert risk_category(0.70) == "MEDIUM" and risk_category(0.71) == "HIGH"
    assert risk_category(0.2, low=0.1, high=0.3) == "MEDIUM"


def test_storage_roundtrip_and_dedupe(storage, mock_records):
    save_record(storage, mock_records[0]); save_record(storage, mock_records[0])
    assert len(load_records(storage)) == 1
    with pytest.raises(ValueError):
        storage.write_bytes("../escape", b"x")
    with pytest.raises(FileNotFoundError):
        storage.read_bytes("missing.json")


def test_validate_dataset_rejects_non_api_source(mock_records):
    df, _ = build_dataset(mock_records)
    validate_dataset(df)
    df2 = df.copy(); df2["data_source"] = "unit_test_mock"
    with pytest.raises(ValueError):
        validate_dataset(df2)
    validate_dataset(df2, allow_test_data=True)
    df3 = df.copy(); df3.loc[0, "execution_id"] = None
    with pytest.raises(ValueError):
        validate_dataset(df3)
