# Data dictionary

| Field | Meaning | Availability |
|---|---|---|
| execution_id | PipelineGuard record UUID | At collection |
| cloudflare_build_uuid | Cloudflare-issued build identifier | After trigger response |
| commit_sha | Commit submitted to the Preview trigger | Before build |
| branch | Experiment branch | Before build |
| timestamp | Cloudflare build creation timestamp | After build metadata retrieval |
| features_json | JSON of prediction-time features | Before build |
| prediction_probability | Predicted failure probability, nullable if no model | Before build |
| predicted_label | Predicted class, nullable if no model | Before build |
| actual_build_status | Cloudflare-reported status | After build |
| actual_build_outcome | success, failure, cancelled, or incomplete | After build |
| actual_duration | Measured duration in seconds, if returned | After build |
| experiment_scenario | Experiment annotation only, never a feature | Configured metadata |
| collection_status | verified, cancelled, incomplete, etc. | After collection |
| raw_object_key | R2 object path | At ingestion |

## Prediction-time features

`changed_files`, `additions`, `deletions`, `python_files_changed`, `test_files_changed`, `dependency_changed`, `config_files_changed`, `previous_build_failed`, `previous_3_failure_count`, `historical_avg_duration`, `commit_age`, and `branch_type` are calculated before the current build trigger. Historical aggregates use only earlier completed records.

## Post-execution labels and prohibited predictors

Current build status, outcome, duration, logs, completion time, test failure count, and injected scenario are post-trigger information. They are labels/metadata only and must not be predictors. `experiment_scenario` is explicitly excluded from the feature list.

`actual_build_outcome=failure` is used only when Cloudflare reports a terminal failed build. API errors, cancelled builds, timeouts, and incomplete records are not binary training labels.
