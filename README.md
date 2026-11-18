# PipelineGuard

**A lightweight ML approach for predicting CI/CD pipeline failures using Google Cloud Platform.**
Every training row comes from a real Google Cloud Build execution. There is no synthetic dataset, no fallback
data, and no hardcoded prediction anywhere in this repo (`tests/test_repo_hygiene.py` enforces the shipped-data part).

> **Status of this ZIP:** fully implemented and unit-tested locally. It has **not** been run against real GCP
> (no credentials were available when it was built), so *zero* real executions exist yet. See "Verification status".

## Layout
```
app/ Flask dashboard        ml/ preprocess/train/predict/evaluate      pg/ shared library (storage, API parsing, provenance)
scripts/ run_experiment, collect_*, aggregate_dataset, setup_gcp, cleanup_gcp, export_report
ci/ steps run inside Cloud Build      cloudbuild.yaml      target_app/ the project that gets built + tested
docs/ methodology & setup      tests/ pytest      monitoring/ alert example      .devcontainer/ Codespaces
```

## 1. GitHub + Codespaces
```bash
unzip PipelineGuard.zip && cd PipelineGuard
git init -b main && git add -A && git commit -m "PipelineGuard"
gh repo create pipelineguard --private --source=. --push      # or create the repo in the browser and `git remote add origin ... && git push -u origin main`
```
Then **Code -> Codespaces -> Create codespace on main**. Dependencies install automatically (Python 3.11).
`.env` is git-ignored; never commit credentials.

## 2. Install Google Cloud CLI (not preinstalled)
```bash
curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update && sudo apt-get install -y google-cloud-cli
```
(Alternative: https://cloud.google.com/sdk/docs/install)

## 3. Local check (no GCP needed)
```bash
pytest -m "not integration"        # 53 unit tests
python run.py                      # http://localhost:8080 -> empty states until real data exists
```

## 4. GCP setup  (read `docs/GCP_SETUP.md` for costs first)
```bash
gcloud auth login --no-launch-browser
gcloud auth application-default login --no-launch-browser     # used by the Python clients
gcloud config set project YOUR_PROJECT_ID
cp .env.example .env     # edit: PG_USE_GCP=true, GCP_PROJECT_ID, GCP_REGION, PG_BUCKET (globally unique)
python scripts/setup_gcp.py --dry-run     # review
python scripts/setup_gcp.py               # enables APIs, creates bucket, grants least-privilege roles
PG_RUN_INTEGRATION=1 pytest -m integration
```
Billing must be enabled on the project (a free-trial billing account is fine).

## 5. Five real runs, then train
```bash
python scripts/run_experiment.py --count 5        # asks y/N; prints a cost warning
python scripts/aggregate_dataset.py               # verified records -> dataset/real_pipeline_history.csv
python ml/train.py && python ml/evaluate.py       # states plainly when data is insufficient
```
Interrupted? `python scripts/run_experiment.py --resume EXPERIMENT_ID` (no duplicate builds).

## 6. The 300-run experiment (never starts automatically)
```bash
python scripts/run_experiment.py --count 300 --concurrency 3 --confirm "RUN 300 BUILDS"
python scripts/aggregate_dataset.py && python ml/train.py && python ml/evaluate.py
python scripts/export_report.py                   # reports/experiment_report.md
```
Use `--dry-run` to see the scenario plan and cost warning without touching the cloud.
Once a model exists, Cloud Build stage 4 downloads it from the bucket and writes an **advisory** risk report
(`--blocking-mode` is experimental, off by default).

## 7. Deploy the dashboard to Cloud Run
```bash
gcloud run deploy pipelineguard --source . --region YOUR_REGION --no-allow-unauthenticated \
  --set-env-vars PG_USE_GCP=true,GCP_PROJECT_ID=YOUR_PROJECT_ID,PG_BUCKET=YOUR_BUCKET,GCP_REGION=YOUR_REGION \
  --min-instances 0 --max-instances 1 --memory 512Mi
gcloud run services proxy pipelineguard --region YOUR_REGION          # private access at http://localhost:8080
gcloud run services describe pipelineguard --region YOUR_REGION --format 'value(status.url)'
gcloud run services logs read pipelineguard --region YOUR_REGION --limit 50
```

## 8. Cleanup
```bash
python scripts/cleanup_gcp.py --dry-run
python scripts/cleanup_gcp.py        # typed confirmation; never deletes the project
```

## Verification status (honest)
Verified here: unit tests (53), Flask startup + `/health`, CLI refusal paths without GCP, `cloudbuild.yaml` parses and
converts to a `Build` proto, and each failure scenario fails at its intended CI step when the `ci/` scripts are run locally.
**Not verified (needs your GCP project):** integration tests, actual Cloud Build submission/polling, GCS I/O,
`setup_gcp.py`/`cleanup_gcp.py` against a live project, Cloud Run deploy, Cloud Monitoring/Logging queries,
and in-build model prediction. Expect to fix small environment issues (IAM, quotas) on first contact.
