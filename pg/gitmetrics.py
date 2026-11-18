"""Real Git change metrics computed from an actual commit diff (no estimation)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
_DEP_FILE = re.compile(r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|setup\.py|setup\.cfg|Pipfile|poetry\.lock)$")
_TEST_FILE = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.py$)")


def git(repo, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def is_test_path(path: str) -> bool:
    return bool(_TEST_FILE.search(path)) and path.endswith(".py")


def is_dependency_path(path: str) -> bool:
    return bool(_DEP_FILE.search(path))


def parse_numstat(text: str) -> list[tuple[int, int, str]]:
    rows = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, d, path = parts
        rows.append((0 if a == "-" else int(a), 0 if d == "-" else int(d), path))
    return rows


def metrics_from_numstat(rows) -> dict:
    return {
        "files_changed": len(rows),
        "lines_added": sum(r[0] for r in rows),
        "lines_deleted": sum(r[1] for r in rows),
        "python_files_changed": sum(1 for r in rows if r[2].endswith(".py")),
        "test_files_changed": sum(1 for r in rows if is_test_path(r[2])),
        "dependency_changes": sum(r[0] + r[1] for r in rows if is_dependency_path(r[2])),
    }


def count_known_tests(repo, rev: str, tests_pathspec=("target_app/tests",)) -> int:
    """Number of `def test_*` functions that existed at `rev` (i.e. before the change under test)."""
    res = git(repo, "grep", "-E", r"^\s*(async\s+)?def test_", rev, "--", *tests_pathspec, check=False)
    if res.returncode == 1:
        return 0
    if res.returncode != 0:
        raise RuntimeError(res.stderr)
    return len([l for l in res.stdout.splitlines() if l.strip()])


def commit_metrics(repo, commit="HEAD", base=None, pathspec=("target_app",), tests_pathspec=("target_app/tests",)) -> dict:
    sha = git(repo, "rev-parse", commit).stdout.strip()
    if base is None:
        parent = git(repo, "rev-parse", "--verify", "-q", f"{sha}^", check=False)
        base = parent.stdout.strip() if parent.returncode == 0 else EMPTY_TREE
    numstat = git(repo, "diff", "--numstat", "--no-renames", base, sha, "--", *pathspec).stdout
    out = metrics_from_numstat(parse_numstat(numstat))
    out["known_test_count"] = count_known_tests(repo, base, tests_pathspec)
    out["commit_sha"] = sha
    out["base_commit"] = base
    return out
