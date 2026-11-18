# Architecture

```
Runner (scripts/run_experiment.py)
  1. applies a real code change to workspace/<exp>/repo and commits it (git)
  2. measures Git metrics from that commit's diff; computes history features from already-collected records
  3. uploads `git archive` of the commit to GCS and submits a Cloud Build (API); features + scenario ride
     along as build substitutions, so the Cloud Build record is self-describing
Cloud Build (cloudbuild.yaml)  env-init -> git-metadata -> fetch-model -> predict (advisory) -> upload-prediction
  -> risk-gate -> install-dependencies -> config-check -> build -> unit-tests -> report
Runner polls get_build until terminal, then stores ONE raw JSON per execution: raw/builds/<id>.json
aggregate_dataset.py: verify provenance -> de-duplicate -> recompute history chronologically -> CSV
ml/train.py: chronological split -> Logistic Regression + Random Forest -> models/*.joblib, reports/model_metrics.json
Flask (Cloud Run): reads CSV/metrics/progress from storage; predicts with models/ from storage
```
Storage keys: `raw/builds/`, `experiments/<id>/progress.json`, `datasets/`, `models/`, `reports/predictions/`, `source/`.
`pg/storage.py` selects local `storage/` (empty by default) or the GCS bucket (`PG_USE_GCP=true`).
Stage 3 "historical metrics retrieval" is performed by the runner at submission time (a build's source archive has no
history) and handed to the build as substitutions; the model fetch in the build is stage 3's second half.
Cloud Build cannot run later steps after a failure, so failed builds produce no `report` output; the authoritative
outcome is always the Cloud Build API record.
