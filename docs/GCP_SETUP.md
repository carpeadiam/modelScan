# GCP setup, costs and cleanup

**APIs enabled by `setup_gcp.py`:** Cloud Build, Cloud Run, Cloud Storage, Cloud Logging, Cloud Monitoring, Artifact Registry
(the last is used by `gcloud run deploy --source`).

**What can cost money** (verify current numbers; they change):
- *Cloud Build:* Google's pricing page lists 2,500 free build-minutes per month per billing account for `e2-standard-2` in
  the default pool (a promotional tier that "is subject to change"), then $0.006/minute; queue time is not billed; the
  default pool allows up to 10 concurrent builds. https://cloud.google.com/build/pricing
  Each build here installs pytest (and scikit-learn once a model exists), so durations are likely a few minutes;
  the runner prints a cost estimate from *measured* durations once past builds exist (unmeasured assumption before that).
  300 builds x N minutes must be compared with the remaining free minutes; free-trial credits may cover overage.
- *Cloud Storage:* tiny (KBs per run plus ~KB source archives); free-tier eligibility depends on region/class.
- *Cloud Run / Artifact Registry / Logging / Monitoring:* low for a demo (`--min-instances 0`), but not guaranteed free.
- A billing account is required even for the free trial. Nothing in this repo upgrades billing.

**Quotas.** Check IAM & Admin -> Quotas for Cloud Build concurrent builds and API rate limits before using
`--concurrency` above 1-2; the runner backs off on 429s but cannot read your quota.

**Roles.** You need Cloud Build Editor (or Owner) and Storage Admin on the bucket. `setup_gcp.py` grants the default
compute service account (default Cloud Build identity in many projects; verify under Cloud Build -> Settings) bucket
Object Admin plus project-level `logging.logWriter`, `logging.viewer`, `monitoring.viewer`. If your project uses a custom
build service account, grant it the same roles and tell the runner nothing else changes.

**Authentication.** Prefer user OAuth: `gcloud auth login` + `gcloud auth application-default login`. In Codespaces use
`--no-launch-browser`. Do not create or commit service-account keys.

**Teardown.** `python scripts/cleanup_gcp.py` (labelled bucket + Cloud Run service; optional `--include-source-repo`).
Build history cannot be deleted. To stop all charges, delete the project in the console yourself (the script never does).
Verify nothing remains: `gcloud run services list`, `gcloud storage buckets list`, `gcloud artifacts repositories list`.
