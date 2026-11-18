import json
import re
from pathlib import Path

import yaml

from pg.features import FEATURE_COLUMNS, FORBIDDEN_COLUMNS, FEATURE_SUBSTITUTIONS
from pg.scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "cloudbuild.yaml").read_text())
STEPS = {s["id"]: s for s in CFG["steps"]}


def test_required_stages_in_order():
    ids = [s["id"] for s in CFG["steps"]]
    for a, b in [("env-init", "git-metadata"), ("git-metadata", "predict"), ("predict", "install-dependencies"),
                 ("install-dependencies", "build"), ("build", "unit-tests"), ("unit-tests", "report")]:
        assert ids.index(a) < ids.index(b)
    assert ids.index("predict") < ids.index("build")   # prediction happens BEFORE build/test


def test_advisory_by_default():
    assert CFG["substitutions"]["_BLOCKING_MODE"] == "false"
    assert "exit 0" in (ROOT / "ci/03_predict.sh").read_text()


def test_scenario_never_reaches_prediction_steps():
    for sid in ("git-metadata", "fetch-model", "predict", "upload-prediction", "risk-gate"):
        env = " ".join(STEPS[sid].get("env", []))
        assert "SCENARIO" not in env and "_SCENARIO" not in env
    for f in ("ci/01_git_metadata.py", "ci/03_predict.sh", "ci/05_risk_gate.py"):
        assert "scenario" not in (ROOT / f).read_text().lower()


def test_all_substitutions_used_are_declared():
    used = set(re.findall(r"\$\{(_[A-Z0-9_]+)\}", (ROOT / "cloudbuild.yaml").read_text()))
    assert used <= set(CFG["substitutions"])
    assert set(FEATURE_SUBSTITUTIONS.values()) <= set(CFG["substitutions"])


def test_every_scenario_is_implemented_in_ci_and_expected_steps_exist():
    sh = (ROOT / "ci/scenarios.sh").read_text()
    for name, meta in SCENARIOS.items():
        assert name in sh
        if meta["expected_failing_step"]:
            assert meta["expected_failing_step"] in STEPS


def test_referenced_ci_scripts_exist():
    for s in CFG["steps"]:
        for arg in s["args"]:
            if arg.startswith("ci/"):
                assert (ROOT / arg).exists(), arg


def test_prediction_model_features_exclude_post_execution_fields():
    assert not set(FEATURE_COLUMNS) & set(FORBIDDEN_COLUMNS)


def test_cloudbuild_yaml_converts_to_build_proto():
    from google.cloud.devtools import cloudbuild_v1  # skipped silently if library missing
    b = cloudbuild_v1.Build.from_json(json.dumps(CFG))
    assert len(b.steps) == len(CFG["steps"]) and b.timeout.seconds == 1200
