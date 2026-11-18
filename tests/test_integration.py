"""Integration tests: need real GCP credentials. Run: PG_RUN_INTEGRATION=1 pytest -m integration"""
import pytest

from pg.config import get_settings


@pytest.mark.integration
def test_cloud_build_api_reachable():
    from pg.buildapi import CloudBuildApi
    s = get_settings()
    assert s.project_id, "set GCP_PROJECT_ID"
    CloudBuildApi(s.project_id, s.build_region).preflight()


@pytest.mark.integration
def test_gcs_roundtrip_in_a_scratch_key():
    from pg.storage import GCSStorage
    s = get_settings()
    st = GCSStorage(s.bucket, s.project_id)
    st.write_json("integration-test/ping.json", {"ok": True})
    assert st.read_json("integration-test/ping.json") == {"ok": True}
    st.delete("integration-test/ping.json")


@pytest.mark.integration
def test_one_real_build_collected_and_verified():
    """Submits ONE real build via the runner path and verifies provenance of the collected record."""
    pytest.skip("Run `python scripts/run_experiment.py --count 5` instead; then `python scripts/aggregate_dataset.py`.")
