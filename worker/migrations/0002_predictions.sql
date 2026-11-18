CREATE TABLE IF NOT EXISTS predictions (
  execution_id TEXT PRIMARY KEY,
  commit_sha TEXT NOT NULL,
  branch TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  features_json TEXT NOT NULL,
  prediction_probability REAL,
  predicted_label INTEGER,
  model_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp DESC);
