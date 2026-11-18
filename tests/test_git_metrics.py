import subprocess

from pg.gitmetrics import commit_metrics, is_dependency_path, is_test_path, parse_numstat, metrics_from_numstat

ID = ["-c", "user.name=t", "-c", "user.email=t@t"]


def g(repo, *a):
    subprocess.run(["git", "-C", str(repo), *ID, *a], check=True, capture_output=True)


def test_numstat_parsing():
    rows = parse_numstat("3\t1\tapp/a.py\n-\t-\timg.png\n2\t0\ttests/test_a.py\n4\t0\trequirements.txt\n")
    m = metrics_from_numstat(rows)
    assert m == {"files_changed": 4, "lines_added": 9, "lines_deleted": 1, "python_files_changed": 2,
                 "test_files_changed": 1, "dependency_changes": 4}


def test_path_classifiers():
    assert is_test_path("target_app/tests/test_x.py") and not is_test_path("src/x.py")
    assert is_dependency_path("target_app/requirements.txt") and not is_dependency_path("a.py")


def test_commit_metrics_on_real_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tests").mkdir(); (tmp_path / "tests/test_a.py").write_text("def test_a():\n    pass\n")
    g(tmp_path, "add", "-A"); g(tmp_path, "commit", "-qm", "one")
    (tmp_path / "m.py").write_text("x = 1\ny = 2\n"); (tmp_path / "requirements.txt").write_text("six\n")
    (tmp_path / "tests/test_a.py").write_text("def test_a():\n    pass\n\ndef test_b():\n    pass\n")
    g(tmp_path, "add", "-A"); g(tmp_path, "commit", "-qm", "two")
    m = commit_metrics(tmp_path, pathspec=(".",), tests_pathspec=("tests",))
    assert m["files_changed"] == 3 and m["lines_added"] == 5 + 1 - 0 and m["python_files_changed"] == 2
    assert m["test_files_changed"] == 1 and m["dependency_changes"] == 1 and m["known_test_count"] == 1
    first = commit_metrics(tmp_path, "HEAD~1", pathspec=(".",), tests_pathspec=("tests",))
    assert first["known_test_count"] == 0 and first["files_changed"] == 1
