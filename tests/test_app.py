import json

import pytest

from app import create_app
from ml.train import train
from pg.dataset import build_dataset
from pg.records import save_record


@pytest.fixture
def client(storage):
    return create_app({"PG_STORAGE": storage, "TESTING": True}).test_client()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/", "/predict", "/history", "/models", "/experiments", "/monitoring"])
def test_pages_render_empty_state_without_data(client, path):
    r = client.get(path)
    assert r.status_code == 200
    if path in ("/", "/history", "/models", "/experiments"):
        assert b"No real data yet" in r.data


def test_api_empty(client):
    assert client.get("/api/overview").get_json() == {"empty": True}
    assert client.get("/api/history").get_json() == []
    assert client.get("/api/metrics").status_code == 404
    assert client.post("/api/predict", json={"features": {}}).status_code == 404


def test_dashboard_reads_collected_data_and_predicts(client, storage, mock_records):
    for r in mock_records:
        save_record(storage, r)
    from scripts_helpers import aggregate_into
    df = aggregate_into(storage)
    assert client.get("/api/overview").get_json()["total"] == len(df)
    assert client.get("/").status_code == 200 and b"Verified executions" in client.get("/").data
    # model trained on MOCK rows inside a unit test only
    d = df.copy(); d["data_source"] = "unit_test_mock"
    train(d, storage, allow_test_data=True)
    assert client.get("/models").status_code == 200
    r = client.post("/api/predict", json={"features": {"files_changed": 5}})
    assert r.status_code == 200 and r.get_json()["risk_category"] in {"LOW", "MEDIUM", "HIGH"}
    assert client.post("/api/predict", json={"features": {"build_duration": 1}}).status_code == 400
    page = client.post("/predict", data={"files_changed": "4", "model": "random_forest"})
    assert b"Failure probability" in page.data
