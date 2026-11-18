#!/usr/bin/env python3
"""Enable required APIs, create the bucket, grant least-privilege roles. Shows every command first.

  python scripts/setup_gcp.py --dry-run     # print only
  python scripts/setup_gcp.py               # asks for confirmation
"""
import _bootstrap  # noqa: F401
import argparse
import shlex
import subprocess
import sys

from pg.config import get_settings

APIS = ["cloudbuild.googleapis.com", "run.googleapis.com", "storage.googleapis.com", "logging.googleapis.com",
        "monitoring.googleapis.com", "artifactregistry.googleapis.com"]


def sh(cmd, check=True):
    print("$", " ".join(shlex.quote(c) for c in cmd))
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    if not (s.project_id and s.bucket):
        sys.exit("Set GCP_PROJECT_ID and PG_BUCKET in .env first (see .env.example).")
    num = "<PROJECT_NUMBER>" if a.dry_run else sh(["gcloud", "projects", "describe", s.project_id,
                                                     "--format=value(projectNumber)"]).stdout.strip()
    sa = f"{num}-compute@developer.gserviceaccount.com"   # default Cloud Build + Cloud Run runtime identity
    member = f"serviceAccount:{sa}"
    plan = [
        ["gcloud", "services", "enable", *APIS, f"--project={s.project_id}"],
        ["gcloud", "storage", "buckets", "create", f"gs://{s.bucket}", f"--project={s.project_id}",
         f"--location={s.region}", "--uniform-bucket-level-access"],
        ["gcloud", "storage", "buckets", "update", f"gs://{s.bucket}", "--update-labels=app=pipelineguard"],
        ["gcloud", "storage", "buckets", "add-iam-policy-binding", f"gs://{s.bucket}", f"--member={member}",
         "--role=roles/storage.objectAdmin"],
        ["gcloud", "projects", "add-iam-policy-binding", s.project_id, f"--member={member}",
         "--role=roles/logging.logWriter", "--condition=None"],
        ["gcloud", "projects", "add-iam-policy-binding", s.project_id, f"--member={member}",
         "--role=roles/monitoring.viewer", "--condition=None"],
        ["gcloud", "projects", "add-iam-policy-binding", s.project_id, f"--member={member}",
         "--role=roles/logging.viewer", "--condition=None"],
    ]
    print("\nPlanned changes (no billing upgrade, no paid resources beyond the bucket):")
    for c in plan:
        print("  ", " ".join(c))
    if a.dry_run:
        return
    if not a.yes and input("\nApply these changes to project %s? [y/N] " % s.project_id).lower() != "y":
        sys.exit("Aborted.")
    for c in plan:
        r = sh(c, check=False)
        if r.returncode:
            print("  !", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "failed")
            if "buckets create" in " ".join(c) and "already" in r.stderr.lower():
                continue
    print("\nDone. Next: gcloud auth application-default login ; python scripts/run_experiment.py --count 5")


if __name__ == "__main__":
    main()
