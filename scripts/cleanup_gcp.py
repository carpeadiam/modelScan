#!/usr/bin/env python3
"""Delete ONLY PipelineGuard resources (Cloud Run service, labelled bucket). Never the project.

  python scripts/cleanup_gcp.py --dry-run
  python scripts/cleanup_gcp.py                         # typed confirmation required
  python scripts/cleanup_gcp.py --include-source-repo   # also the Artifact Registry repo created by `run deploy --source`
"""
import _bootstrap  # noqa: F401
import argparse
import json
import subprocess
import sys

from pg.config import get_settings


def run(cmd, check=False):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-source-repo", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    if not (s.project_id and s.bucket):
        sys.exit("Set GCP_PROJECT_ID and PG_BUCKET first.")
    targets = []
    svc = run(["gcloud", "run", "services", "describe", s.service_name, f"--region={s.region}",
               f"--project={s.project_id}", "--format=value(metadata.name)"])
    if svc.returncode == 0 and svc.stdout.strip():
        targets.append(("Cloud Run service", s.service_name,
                        ["gcloud", "run", "services", "delete", s.service_name, f"--region={s.region}",
                         f"--project={s.project_id}", "--quiet"]))
    b = run(["gcloud", "storage", "buckets", "describe", f"gs://{s.bucket}", "--format=json"])
    if b.returncode == 0:
        labels = (json.loads(b.stdout).get("labels") or {})
        if labels.get("app") == "pipelineguard":
            targets.append(("Cloud Storage bucket (and ALL objects)", s.bucket,
                            ["gcloud", "storage", "rm", "--recursive", f"gs://{s.bucket}", "--quiet"]))
        else:
            print(f"SKIPPING gs://{s.bucket}: it lacks label app=pipelineguard (not created by setup_gcp.py).")
    if a.include_source_repo:
        targets.append(("Artifact Registry repo", "cloud-run-source-deploy",
                        ["gcloud", "artifacts", "repositories", "delete", "cloud-run-source-deploy",
                         f"--location={s.region}", f"--project={s.project_id}", "--quiet"]))
    if not targets:
        print("Nothing to delete."); return
    print(f"Project: {s.project_id} (the project itself will NOT be deleted)\nWould delete:")
    for kind, name, _ in targets:
        print(f"  - {kind}: {name}")
    print("Not deletable: Cloud Build history (retained by Google). Local workspace/ and storage/ are untouched.")
    if a.dry_run:
        return
    if input(f'Type "DELETE {s.project_id}" to confirm: ').strip() != f"DELETE {s.project_id}":
        sys.exit("Aborted.")
    for kind, name, cmd in targets:
        r = run(cmd)
        print(("deleted " if r.returncode == 0 else "FAILED  ") + f"{kind} {name}" +
              ("" if r.returncode == 0 else f": {r.stderr.strip()[-200:]}"))


if __name__ == "__main__":
    main()
