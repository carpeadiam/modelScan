CREATE TABLE IF NOT EXISTS executions (
  execution_id TEXT PRIMARY KEY,
  cloudflare_build_uuid TEXT NOT NULL UNIQUE,
  commit_sha TEXT NOT NULL,
  branch TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  features_json TEXT NOT NULL,
  prediction_probability REAL,
  predicted_label INTEGER,
  actual_build_status TEXT,
  actual_build_outcome TEXT NOT NULL,
  actual_duration REAL,
  experiment_scenario TEXT,
  collection_status TEXT NOT NULL,
  raw_object_key TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executions_timestamp ON executions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_executions_branch ON executions(branch);
CREATE INDEX IF NOT EXISTS idx_executions_commit ON executions(commit_sha);
