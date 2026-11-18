"""Workload commits: real, working code changes applied to target_app and committed to git.

The change *inputs* (size, whether tests/dependencies change) are chosen from a seeded RNG for
experimental design. Every Git metric is then MEASURED from the resulting real commit diff, and every
outcome comes from Cloud Build. Nothing here assigns a label or an outcome.
"""
from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path

from .config import ROOT
from .gitmetrics import git

DEP_POOL = ["six==1.16.0", "python-dateutil==2.9.0.post0", "packaging==24.1",
            "idna==3.10", "attrs==24.2.0", "toml==0.10.2"]
COPY_ITEMS = ["target_app", "ci", "ml", "pg", "requirements-ml.txt"]
_IDENT = ["-c", "user.name=PipelineGuard", "-c", "user.email=pipelineguard@example.invalid"]


def init_workspace(repo: Path, source_root: Path = ROOT) -> str:
    """Create a git repo seeded from the project (baseline commit). Returns baseline SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    for item in COPY_ITEMS:
        src, dst = source_root / item, repo / item
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "generated"))
        else:
            shutil.copy2(src, dst)
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "add", "-A")
    git(repo, *_IDENT, "commit", "-q", "-m", "baseline")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_module(path: Path, run: int, rng: random.Random, n_funcs: int):
    lines, tests = [f'"""Generated workload module (run {run})."""', ""], []
    for k in range(n_funcs):
        reps, coef = rng.randint(2, 9), rng.randint(1, 7)
        name = f"fn_r{run}_{k}"
        lines += [f"def {name}(x):", f'    """Generated workload function {name}."""', "    total = 0",
                  f"    for i in range({reps}):", f"        total += (x + i) * {coef}", "    return total", ""]
        arg = rng.randint(0, 20)
        expected = sum((arg + i) * coef for i in range(reps))
        tests.append((name, arg, expected))
    return "\n".join(lines) + "\n", tests


def apply_change(repo: Path, run_index: int, seed: str) -> dict:
    rng = random.Random(f"{seed}:change:{run_index}")
    gen = repo / "target_app" / "src" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "__init__.py").touch()
    n_funcs = rng.randint(1, 15)
    mod = f"mod_r{run_index}"
    code, tests = _write_module(gen / f"{mod}.py", run_index, rng, n_funcs)
    (gen / f"{mod}.py").write_text(code)
    desc = {"module": mod, "functions": n_funcs, "tests_added": 0, "dependency_added": None}
    if rng.random() < 0.6:  # add tests that exercise the new code
        body = [f"from target_app.src.generated import {mod}", ""]
        for name, arg, expected in tests:
            body += [f"def test_{name}():", f"    assert {mod}.{name}({arg}) == {expected}", ""]
        (repo / "target_app" / "tests" / f"test_generated_r{run_index}.py").write_text("\n".join(body))
        desc["tests_added"] = len(tests)
    if rng.random() < 0.15:  # real dependency change
        req = repo / "target_app" / "requirements.txt"
        present = set(req.read_text().split())
        choices = [d for d in DEP_POOL if d not in present]
        if choices:
            dep = rng.choice(choices)
            req.write_text(req.read_text().rstrip("\n") + f"\n{dep}\n")
            desc["dependency_added"] = dep
    git(repo, "add", "-A", "target_app")
    git(repo, *_IDENT, "commit", "-q", "-m", f"workload change for run {run_index}")
    return desc
