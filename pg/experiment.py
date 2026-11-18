"""Experiment progress tracking and the resumable runner."""
from __future__ import annotations

import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from .buildapi import TERMINAL, is_retriable
from .records import make_record, save_record, load_records
from .storage import Storage

PROGRESS_FMT = "experiments/{eid}/progress.json"
FINAL_STATES = {"collected"}


def new_experiment_id() -> str:
    return datetime.now(timezone.utc).strftime("exp-%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def retry_with_backoff(fn: Callable, retries: int = 5, base: float = 2.0, cap: float = 60.0,
                       sleep: Callable = time.sleep, retriable=is_retriable):
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if attempt == retries or not retriable(exc):
                raise
            sleep(min(cap, base * (2 ** attempt)))


class Progress:
    """Thread-safe, persisted experiment state (one JSON object per experiment)."""

    def __init__(self, storage: Storage, data: dict):
        self.storage, self.data, self._lock = storage, data, threading.RLock()

    @classmethod
    def create(cls, storage, experiment_id, scenarios: List[str], config: dict) -> "Progress":
        data = {"experiment_id": experiment_id, "created_at": now_iso(), "updated_at": now_iso(),
                "requested": len(scenarios), "config": config,
                "runs": [{"run_index": i, "scenario": s, "state": "planned", "commit_sha": None,
                          "build_id": None, "build_status": None, "note": None}
                         for i, s in enumerate(scenarios)]}
        p = cls(storage, data)
        p.save()
        return p

    @classmethod
    def load(cls, storage, experiment_id) -> "Progress":
        key = PROGRESS_FMT.format(eid=experiment_id)
        data = storage.read_json_or_none(key)
        if data is None:
            raise FileNotFoundError(f"No saved progress for experiment {experiment_id}")
        return cls(storage, data)

    def save(self):
        with self._lock:
            self.data["updated_at"] = now_iso()
            self.storage.write_json(PROGRESS_FMT.format(eid=self.data["experiment_id"]), self.data)

    def run(self, idx: int) -> dict:
        return self.data["runs"][idx]

    def update(self, idx: int, **fields):
        with self._lock:
            self.data["runs"][idx].update(fields)
            self.save()

    def pending(self) -> List[int]:
        return [r["run_index"] for r in self.data["runs"] if r["state"] not in FINAL_STATES]

    def summary(self) -> dict:
        runs = self.data["runs"]
        collected = [r for r in runs if r["state"] == "collected"]
        return {
            "experiment_id": self.data["experiment_id"], "requested": self.data["requested"],
            "collected": len(collected),
            "successful": sum(r["build_status"] == "SUCCESS" for r in collected),
            "failed": sum(r["build_status"] == "FAILURE" for r in collected),
            "other_terminal": sum(r["build_status"] not in ("SUCCESS", "FAILURE") for r in collected),
            "pending": len(runs) - len(collected),
            "by_state": {s: sum(r["state"] == s for r in runs) for s in sorted({r["state"] for r in runs})},
            "progress_pct": round(100 * len(collected) / max(1, len(runs)), 1),
        }


class StopRequested(Exception):
    pass


class ExperimentRunner:
    """Orchestrates real Cloud Build executions. `api` must provide submit/get/find_by_tag."""

    def __init__(self, *, storage: Storage, api, repo, bucket: str, project_id: str, progress: Progress,
                 seed: str, workload, metrics_fn, history_fn, poll_interval=15.0, build_timeout=1800.0,
                 sleep=time.sleep, config: Optional[dict] = None, log=print):
        self.storage, self.api, self.repo, self.bucket = storage, api, repo, bucket
        self.project_id, self.progress, self.seed = project_id, progress, seed
        self.workload, self.metrics_fn, self.history_fn = workload, metrics_fn, history_fn
        self.poll_interval, self.build_timeout, self.sleep = poll_interval, build_timeout, sleep
        self.config, self.log = config, log
        self.stop = threading.Event()
        self._git_lock = threading.Lock()

    def tag(self, idx):  # unique per run -> lets a resumed run detect an already-submitted build
        return f"pg-run-{self.progress.data['experiment_id']}-{idx}"

    def _check_stop(self):
        if self.stop.is_set():
            raise StopRequested()

    # --- phases ---------------------------------------------------------------------------
    def _prepare(self, idx):
        run = self.progress.run(idx)
        if run.get("commit_sha") and run.get("features"):
            return
        with self._git_lock:
            self.workload(self.repo, idx, self.seed)
            m = self.metrics_fn(self.repo)
        hist = self.history_fn()
        feats = {k: m[k] for k in ("files_changed", "lines_added", "lines_deleted", "python_files_changed",
                                   "test_files_changed", "dependency_changes", "known_test_count")}
        feats.update(hist)
        self.progress.update(idx, state="prepared", commit_sha=m["commit_sha"], features=feats)

    def _submit(self, idx):
        run = self.progress.run(idx)
        if run.get("build_id"):
            return
        existing = retry_with_backoff(lambda: self.api.find_by_tag(self.tag(idx)))
        if existing:  # interrupted after create_build but before progress was saved -> adopt, don't duplicate
            self.progress.update(idx, state="submitted", build_id=existing[0]["id"], note="adopted existing build")
            return
        from .features import FEATURE_SUBSTITUTIONS
        eid = self.progress.data["experiment_id"]
        subs = {"_SCENARIO": run["scenario"], "_EXPERIMENT_ID": eid, "_RUN_INDEX": idx,
                "_COMMIT_SHA": run["commit_sha"], "_BUCKET": self.bucket}
        subs.update(self.progress.data["config"].get("substitutions", {}))
        for col, sub in FEATURE_SUBSTITUTIONS.items():
            v = run["features"].get(col)
            subs[sub] = "" if v is None else v
        key = f"source/{eid}/run-{idx}.tar.gz"
        self.storage.write_bytes(key, self.repo_archive(run["commit_sha"]), "application/gzip")
        tags = ["pipelineguard", f"pg-exp-{eid}", self.tag(idx)]
        build_id = retry_with_backoff(lambda: self.api.submit(self.config_yaml, subs, tags, self.bucket, key))
        self.progress.update(idx, state="submitted", build_id=build_id, submitted_at=now_iso())
        self.log(f"[run {idx}] submitted build {build_id} scenario={run['scenario']}")

    def _poll(self, idx):
        run = self.progress.run(idx)
        deadline = time.monotonic() + self.build_timeout
        while True:
            self._check_stop()
            build = retry_with_backoff(lambda: self.api.get(run["build_id"]))
            if build.get("status") in TERMINAL:
                return build
            if time.monotonic() > deadline:
                self.progress.update(idx, state="poll_timeout", note="polling timed out; resume to continue")
                raise TimeoutError(f"run {idx} polling timeout")
            self.sleep(self.poll_interval)

    def _collect(self, idx, build):
        rec = make_record(build, self.project_id)
        save_record(self.storage, rec)
        self.progress.update(idx, state="collected", build_status=build["status"])
        self.log(f"[run {idx}] collected {build['id']} -> {build['status']}")

    repo_archive = None      # injected by caller: sha -> tar.gz bytes
    config_yaml = None       # injected by caller: parsed cloudbuild.yaml dict

    def process(self, idx: int) -> str:
        """Drive one run through its remaining phases. Safe to call again after interruption."""
        try:
            if self.progress.run(idx)["state"] == "collected":
                return "skipped"
            self._check_stop()
            self._prepare(idx)
            self._check_stop()
            self._submit(idx)
            build = self._poll(idx)
            self._collect(idx, build)
            return "collected"
        except StopRequested:
            return "interrupted"
        except TimeoutError:
            return "poll_timeout"
        except Exception as exc:  # noqa: BLE001
            if self.progress.run(idx)["state"] in ("planned", "prepared"):
                self.progress.update(idx, state="submit_failed", note=f"{type(exc).__name__}: {exc}")
            else:
                self.progress.update(idx, note=f"{type(exc).__name__}: {exc}")
            self.log(f"[run {idx}] ERROR {type(exc).__name__}: {exc}")
            return "error"
