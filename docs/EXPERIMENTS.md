# Experiments

| Step | Command | Notes |
|---|---|---|
| Plan only | `run_experiment.py --count 300 --dry-run` | no cloud calls |
| Pilot | `--count 5` | measures real build duration for cost estimates |
| Medium | `--count 50 --concurrency 2` | |
| Full | `--count 300 --concurrency 3 --confirm "RUN 300 BUILDS"` | typed confirmation, cost warning |
| Resume | `--resume EXP_ID` | skips collected runs; adopts builds that were submitted but not recorded (tag lookup) |
| Blocking (experimental) | `--blocking-mode` | HIGH risk fails the `risk-gate` step; those builds are excluded from training |

Safety: `PG_MAX_RUNS` (300), `PG_MAX_CONCURRENCY` (4), exponential backoff on 429/5xx, per-build poll timeout
(`--build-timeout`), Ctrl-C stops submitting and saves progress (in-flight cloud builds keep running; resume collects them).
Scenario mix: `--weights success=0.7,unit_test_failure=0.1,...`. A new model only becomes visible to builds after
`ml/train.py` writes `models/` to the bucket; early runs therefore log "prediction skipped: no trained model".
Suggested order: 5 -> train (expect "insufficient data") -> 50 -> 300 -> retrain -> evaluate -> `export_report.py`.
Rows collected with the model active are ordinary rows; the advisory report never changes the outcome.
