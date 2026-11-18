# Data collection

Raw record (`raw/builds/<execution_id>.json`): `build` (verbatim Cloud Build API response), `parsed` (normalised),
`pipelineguard` (experiment id, run index, scenario, commit, submitted features), `verification` (method, project,
time). One object per execution avoids concurrent-write problems.

`dataset/real_pipeline_history.csv` columns: execution_id, experiment_id, timestamp (build createTime), commit_sha,
the 11 features (see `pg/features.py`), build_duration (start->finish), pipeline_status, failure_type,
injected_scenario, failed_step, data_source (`cloud_build_api`). Labels/analysis fields (last 6) are never features.

**Missing values.** Never invented. `previous_build_failed`, `historical_avg_duration`, `historical_failure_rate`
are empty for the first build; `previous_3_build_failures` is a true count (0 when nothing precedes). Missing start
time -> empty `build_duration`. Rows lacking Git metrics are excluded. Models impute with the training-set median and
add missing-indicator columns *inside* the sklearn pipeline (fit on training data only).

**Timestamps / ordering.** `timestamp` is createTime. History for a row uses builds with finishTime <= that createTime.
In parallel mode the runner's submission-time history can be slightly older than the aggregator's recomputed history;
the CSV (recomputed) is what models train on. The submission-time values remain in the raw record for audit.

**Workload commits.** To obtain varied, real change metrics from a single repository, the runner commits generated
but working code to `workspace/<exp>/repo` (new module, optional tests, optional pinned dependency). The change size
is drawn from a seeded RNG (experimental design); all metrics are *measured* from the real diff. This is a disclosed
design choice (see LIMITATIONS).
