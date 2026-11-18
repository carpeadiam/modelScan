#!/usr/bin/env python3
"""Orchestrate REAL Google Cloud Build executions (never simulated).

  python scripts/run_experiment.py --count 5
  python scripts/run_experiment.py --count 50 --concurrency 3
  python scripts/run_experiment.py --count 300 --concurrency 4        # asks for typed confirmation
  python scripts/run_experiment.py --resume exp-20260101-120000-ab12  # continue an interrupted batch
"""
import _bootstrap  # noqa: F401
import argparse
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from pg.buildapi import CloudBuildApi
from pg.config import ROOT, get_settings
from pg.dataset import history_features
from pg.experiment import ExperimentRunner, Progress, new_experiment_id, now_iso
from pg.gitmetrics import commit_metrics
from pg.provenance import verify_record
from pg.records import load_records
from pg.scenarios import SCENARIOS, parse_weights, plan_scenarios
from pg.storage import get_storage
from pg.workload import apply_change, init_workspace

LARGE_RUN = 100
EST_MIN_ASSUMPTION = 4.0  # ONLY a planning assumption, replaced by measured durations when available


def die(msg: str, code: int = 2):
    print(f"\nSTOPPING: {msg}", file=sys.stderr)
    sys.exit(code)


def measured_avg_minutes(storage):
    durs = [r["parsed"]["duration_seconds"] for r in load_records(storage)
            if verify_record(r)[0] and r["parsed"]["duration_seconds"]]
    return (sum(durs) / len(durs) / 60.0, len(durs)) if durs else (None, 0)


def cost_warning(count, avg_min, n_measured):
    basis = (f"measured average {avg_min:.1f} min over {n_measured} past builds" if avg_min
             else f"UNMEASURED assumption of {EST_MIN_ASSUMPTION} min/build (run --count 5 first to measure)")
    mins = count * (avg_min or EST_MIN_ASSUMPTION)
    print("\n=== COST WARNING ===")
    print(f"{count} builds x ({basis}) ~= {mins:.0f} build-minutes (excludes queue time, which is not billed).")
    print("Cloud Build gives 2,500 free build-minutes/month on e2-standard-2 (default pool) per billing account;")
    print("beyond that ~$0.006/min (verify current pricing: https://cloud.google.com/build/pricing).")
    print("Also billed/limited: Cloud Storage, Cloud Logging above free allotments, Cloud Run if deployed.")
    print("Free-trial credits may apply; this script does NOT guarantee the run is free.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=5, help="number of executions (default 5)")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--seed", default=None, help="seed for scenario plan / workload (default: experiment id)")
    ap.add_argument("--weights", default=None, help="e.g. success=0.6,unit_test_failure=0.4")
    ap.add_argument("--resume", metavar="EXPERIMENT_ID")
    ap.add_argument("--poll-interval", type=float, default=15.0)
    ap.add_argument("--build-timeout", type=float, default=1800.0, help="max seconds to wait per build")
    ap.add_argument("--blocking-mode", action="store_true", help="EXPERIMENTAL: HIGH risk stops the build")
    ap.add_argument("--no-prediction", action="store_true", help="skip the in-build prediction stage")
    ap.add_argument("--yes", action="store_true", help="skip the y/N prompt (not the large-run phrase)")
    ap.add_argument("--confirm", default="", help=f'for count>={LARGE_RUN}: exact phrase "RUN <count> BUILDS"')
    ap.add_argument("--dry-run", action="store_true", help="print the plan only; touches nothing")
    a = ap.parse_args()
    s = get_settings()

    if a.concurrency < 1 or a.concurrency > s.max_concurrency:
        die(f"--concurrency must be 1..{s.max_concurrency} (PG_MAX_CONCURRENCY). Check your Cloud Build quota first.")
    if a.count < 1 or a.count > s.max_runs:
        die(f"--count must be 1..{s.max_runs} (PG_MAX_RUNS).")

    weights = parse_weights(a.weights)
    if a.dry_run:
        plan = plan_scenarios(a.count, weights, a.seed or "dry-run")
        print("Scenario plan:", {k: plan.count(k) for k in SCENARIOS})
        cost_warning(a.count, None, 0)
        return

    if not (s.use_gcp and s.project_id and s.bucket):
        die("Real Cloud Build executions need PG_USE_GCP=true, GCP_PROJECT_ID and PG_BUCKET (see .env.example, "
            "docs/GCP_SETUP.md). No data was generated.")
    storage = get_storage(s)
    api = CloudBuildApi(s.project_id, s.build_region)
    try:
        api.preflight()
    except Exception as exc:  # noqa: BLE001
        die(f"Cloud Build API not usable ({type(exc).__name__}): {exc}\n"
            "Check: `gcloud auth application-default login`, billing enabled, cloudbuild.googleapis.com enabled, "
            "and your account has roles/cloudbuild.builds.editor. No data was generated.")

    if a.resume:
        progress = Progress.load(storage, a.resume)
        eid, count = a.resume, progress.data["requested"]
        seed = progress.data["config"]["seed"]
        repo = ROOT / "workspace" / eid / "repo"
        if not repo.exists() and any(not progress.run(i).get("commit_sha") for i in progress.pending()):
            die(f"Workspace {repo} is missing but unprepared runs remain; cannot resume safely.")
    else:
        eid, count = new_experiment_id(), a.count
        seed = a.seed or eid
        repo = ROOT / "workspace" / eid / "repo"
    avg, n = measured_avg_minutes(storage)
    cost_warning(count, avg, n)
    if count >= LARGE_RUN:
        phrase = f"RUN {count} BUILDS"
        typed = a.confirm or (input(f'Type exactly "{phrase}" to start: ') if sys.stdin.isatty() else "")
        if typed.strip() != phrase:
            die(f'Large run not confirmed. Re-run with --confirm "{phrase}" or type it interactively.')
    elif not a.yes:
        if not sys.stdin.isatty() or input(f"Start {count} real Cloud Build executions? [y/N] ").lower() != "y":
            die("Not confirmed (use --yes to skip this prompt).", 1)

    if not a.resume:
        scenarios = plan_scenarios(count, weights, seed)
        subs = {"_BLOCKING_MODE": str(a.blocking_mode).lower(),
                "_ENABLE_PREDICTION": str(not a.no_prediction).lower()}
        progress = Progress.create(storage, eid, scenarios, {"seed": seed, "weights": weights,
                                   "concurrency": a.concurrency, "substitutions": subs, "project_id": s.project_id})
        init_workspace(repo)
    print(f"Experiment {eid}: {len(progress.pending())} runs to process (resume with --resume {eid})")

    def history():
        prior = sorted((r["parsed"] for r in load_records(storage) if verify_record(r)[0]
                        and r["parsed"]["finish_time"]), key=lambda p: p["finish_time"])
        return history_features(prior)

    runner = ExperimentRunner(storage=storage, api=api, repo=repo, bucket=s.bucket, project_id=s.project_id,
                              progress=progress, seed=seed, workload=apply_change,
                              metrics_fn=lambda r: commit_metrics(r), history_fn=history,
                              poll_interval=a.poll_interval, build_timeout=a.build_timeout)
    runner.config_yaml = yaml.safe_load((ROOT / "cloudbuild.yaml").read_text())
    runner.repo_archive = lambda sha: subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar.gz", sha], capture_output=True, check=True).stdout

    def on_sigint(*_):
        print("\nInterrupt received: finishing in-flight bookkeeping; running builds keep running in the cloud.")
        runner.stop.set()
    signal.signal(signal.SIGINT, on_sigint)

    todo = progress.pending()
    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        results = list(pool.map(runner.process, todo))
    summ = progress.summary()
    summ.update({"finished_at": now_iso(), "results": {r: results.count(r) for r in set(results)},
                 "by_scenario": {k: sum(1 for r in progress.data["runs"] if r["scenario"] == k) for k in SCENARIOS}})
    storage.write_json(f"experiments/{eid}/summary.json", summ)
    print("\n=== EXPERIMENT SUMMARY ===")
    for k, v in summ.items():
        print(f"{k}: {v}")
    if summ["pending"]:
        print(f"\nIncomplete. Resume with: python scripts/run_experiment.py --resume {eid}")
    else:
        print("\nNext: python scripts/aggregate_dataset.py && python ml/train.py")


if __name__ == "__main__":
    main()
