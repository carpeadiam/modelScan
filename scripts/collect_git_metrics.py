#!/usr/bin/env python3
"""Print real Git change metrics for a commit.   python scripts/collect_git_metrics.py --repo . --commit HEAD"""
import _bootstrap  # noqa: F401
import argparse
import json

from pg.gitmetrics import commit_metrics

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=".")
ap.add_argument("--commit", default="HEAD")
ap.add_argument("--base", default=None, help="base commit (default: parent)")
ap.add_argument("--pathspec", nargs="+", default=["."])
ap.add_argument("--tests-pathspec", nargs="+", default=["tests"])
a = ap.parse_args()
print(json.dumps(commit_metrics(a.repo, a.commit, a.base, tuple(a.pathspec), tuple(a.tests_pathspec)), indent=2))
