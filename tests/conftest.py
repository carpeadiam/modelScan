"""Test helpers. EVERYTHING here is a mock used only by unit tests; it is never written to dataset/ or storage/."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pg.records import make_record  # noqa: E402
from pg.storage import LocalStorage  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if os.environ.get("PG_RUN_INTEGRATION") != "1":
        skip = pytest.mark.skip(reason="integration test: set PG_RUN_INTEGRATION=1 and authenticate to GCP")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


def fake_build(i, status="SUCCESS", create="2026-01-01T00:00:%02dZ", dur=60, scenario="success",
               failed_step=None, files=3, extra_subs=None):
    """MOCK Cloud Build API payload (unit tests only)."""
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=10 * i)
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.123456789Z")  # noqa: E731
    steps = [{"id": "unit-tests", "status": "SUCCESS" if status == "SUCCESS" else "FAILURE",
              "timing": {"startTime": fmt(base), "endTime": fmt(base + timedelta(seconds=5))}}]
    if failed_step:
        steps = [{"id": failed_step, "status": "FAILURE", "timing": {}}]
    subs = {"_SCENARIO": scenario, "_EXPERIMENT_ID": "exp-test", "_RUN_INDEX": str(i), "_COMMIT_SHA": f"sha{i}",
            "_FILES_CHANGED": str(files), "_LINES_ADDED": "40", "_LINES_DELETED": "2", "_PY_FILES_CHANGED": "3",
            "_TEST_FILES_CHANGED": "1", "_DEPENDENCY_CHANGES": "0", "_KNOWN_TEST_COUNT": "10"}
    subs.update(extra_subs or {})
    return {"id": f"mock-build-{i:04d}", "projectId": "mock-project", "status": status,
            "name": f"projects/1/locations/global/builds/mock-build-{i:04d}",
            "createTime": fmt(base), "startTime": fmt(base + timedelta(seconds=2)),
            "finishTime": fmt(base + timedelta(seconds=2 + dur)), "steps": steps, "substitutions": subs,
            "tags": ["pipelineguard"]}


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "store")


@pytest.fixture
def mock_records():
    """Alternating outcomes so both classes exist (mock data for unit tests only)."""
    recs = []
    for i in range(40):
        fail = i % 3 == 0
        b = fake_build(i, "FAILURE" if fail else "SUCCESS", scenario="unit_test_failure" if fail else "success",
                       failed_step="unit-tests" if fail else None, files=3 + (i % 5))
        recs.append(make_record(b, "mock-project"))
    return recs
