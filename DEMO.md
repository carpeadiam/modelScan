# Demo script (about 10 minutes, after >= 5 real executions exist)
1. `python run.py` -> **Overview**: counts come from verified Cloud Build executions (empty state before any exist).
2. **History**: click an execution ID; find it in Cloud Build history in the console (provenance).
3. Console -> Cloud Build -> a failed run: show the failing step (e.g. `unit-tests`) and compare with `failure_type`.
4. `python scripts/aggregate_dataset.py` and open `storage/datasets/exclusions.json` to show what was excluded and why.
5. `python ml/train.py && python ml/evaluate.py` -> read the class distribution and the caution banner first.
6. **Predict** page: enter pre-build metrics; note post-execution fields are rejected.
7. **Experiments** page: progress of the current batch. **Monitoring**: only populated on Cloud Run with GCP enabled.
