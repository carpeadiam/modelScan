import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import fake_build
from pg.buildapi import extract_meta
from pg.dataset import history_features
from pg.experiment import ExperimentRunner, Progress, retry_with_backoff
from pg.gitmetrics import commit_metrics
from pg.scenarios import plan_scenarios, DEFAULT_WEIGHTS
from pg.workload import apply_change, init_workspace
from pg.features import FEATURE_SUBSTITUTIONS

ROOT = Path(__file__).resolve().parent.parent


class FakeApi:
    """MOCK Cloud Build client for unit tests: records calls; results are never persisted as real data."""
    def __init__(self):
        self.submitted, self.n = [], 0
    def submit(self, config, subs, tags, bucket, obj):
        self.n += 1
        self.submitted.append({"subs": subs, "tags": tags, "id": f"mock-build-{self.n:04d}"})
        return f"mock-build-{self.n:04d}"
    def get(self, bid):
        s = next(x for x in self.submitted if x["id"] == bid)
        fail = s["subs"]["_SCENARIO"] != "success"
        b = fake_build(int(bid.split("-")[-1]), "FAILURE" if fail else "SUCCESS", scenario=s["subs"]["_SCENARIO"])
        b["id"] = bid
        return b
    def find_by_tag(self, tag):
        return [{"id": s["id"]} for s in self.submitted if tag in s["tags"]]


def make_runner(storage, tmp_path, progress, api, stop_after=None):
    repo = tmp_path / "repo"
    if not repo.exists():
        init_workspace(repo, ROOT)
    r = ExperimentRunner(storage=storage, api=api, repo=repo, bucket="b", project_id="mock-project",
                         progress=progress, seed="t", workload=apply_change,
                         metrics_fn=lambda rp: commit_metrics(rp), history_fn=lambda: history_features([]),
                         poll_interval=0, sleep=lambda s: None)
    r.config_yaml = yaml.safe_load((ROOT / "cloudbuild.yaml").read_text())
    r.repo_archive = lambda sha: subprocess.run(["git", "-C", str(repo), "archive", "--format=tar.gz", sha],
                                                capture_output=True, check=True).stdout
    return r


def test_run_and_resume_without_duplicates(storage, tmp_path):
    plan = plan_scenarios(4, DEFAULT_WEIGHTS, "t")
    prog = Progress.create(storage, "exp-t", plan, {"seed": "t", "substitutions": {}})
    api = FakeApi()
    r = make_runner(storage, tmp_path, prog, api)
    assert r.process(0) == "collected" and r.process(1) == "collected"
    # simulate an interruption: new process, progress reloaded from storage
    prog2 = Progress.load(storage, "exp-t")
    assert prog2.pending() == [2, 3]
    r2 = make_runner(storage, tmp_path, prog2, api)
    for i in prog2.pending():
        r2.process(i)
    assert r2.process(0) == "skipped"
    assert len(api.submitted) == 4 and len({s["id"] for s in api.submitted}) == 4
    s = Progress.load(storage, "exp-t").summary()
    assert s["collected"] == 4 and s["pending"] == 0 and s["progress_pct"] == 100.0
    assert len(storage.list_keys("raw/builds/")) == 4


def test_resume_adopts_already_submitted_build(storage, tmp_path):
    prog = Progress.create(storage, "exp-a", ["success"], {"seed": "t", "substitutions": {}})
    api = FakeApi()
    r = make_runner(storage, tmp_path, prog, api)
    r._prepare(0)
    api.submit({}, {"_SCENARIO": "success"}, ["pipelineguard", r.tag(0)], "b", "x")  # crashed before saving id
    assert r.process(0) == "collected"
    assert len(api.submitted) == 1          # no duplicate build created


def test_stop_request_is_graceful(storage, tmp_path):
    prog = Progress.create(storage, "exp-s", ["success", "success"], {"seed": "t", "substitutions": {}})
    r = make_runner(storage, tmp_path, prog, FakeApi())
    r.stop.set()
    assert r.process(0) == "interrupted" and prog.pending() == [0, 1]


def test_submission_carries_features_and_scenario_in_substitutions(storage, tmp_path):
    prog = Progress.create(storage, "exp-f", ["config_failure"], {"seed": "t", "substitutions": {}})
    api = FakeApi(); r = make_runner(storage, tmp_path, prog, api)
    r.process(0)
    subs = api.submitted[0]["subs"]
    assert subs["_SCENARIO"] == "config_failure" and subs["_FILES_CHANGED"] != "" and subs["_EXPERIMENT_ID"] == "exp-f"
    assert set(FEATURE_SUBSTITUTIONS.values()) <= set(subs)


def test_workload_commit_is_real_and_measurable(tmp_path):
    repo = tmp_path / "r"; init_workspace(repo, ROOT)
    apply_change(repo, 0, "seed")
    m = commit_metrics(repo)
    assert m["files_changed"] >= 2 and m["lines_added"] > 0 and m["known_test_count"] >= 4


def test_backoff_retries_then_raises():
    calls, sleeps = [], []
    def flaky():
        calls.append(1)
        raise RuntimeError("x")
    with pytest.raises(RuntimeError):
        retry_with_backoff(flaky, retries=3, sleep=sleeps.append, retriable=lambda e: True)
    assert len(calls) == 4 and sleeps == [2.0, 4.0, 8.0]
    n = {"c": 0}
    def ok_after_two():
        n["c"] += 1
        if n["c"] < 3:
            raise RuntimeError
        return "done"
    assert retry_with_backoff(ok_after_two, sleep=lambda s: None, retriable=lambda e: True) == "done"
