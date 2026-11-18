from pathlib import Path

def test_d1_schema_has_unique_build_uuid_and_prediction_table():
    root=Path(__file__).parents[1]
    init=(root/'worker/migrations/0001_init.sql').read_text()
    prediction=(root/'worker/migrations/0002_predictions.sql').read_text()
    assert 'cloudflare_build_uuid TEXT NOT NULL UNIQUE' in init
    assert 'CREATE TABLE IF NOT EXISTS predictions' in prediction
