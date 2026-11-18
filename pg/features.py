"""Feature definitions and leakage guards. Pure Python (also imported inside Cloud Build steps)."""
from __future__ import annotations

# Pre-execution features: everything here is knowable BEFORE the build starts.
FEATURE_COLUMNS = [
    "files_changed",
    "lines_added",
    "lines_deleted",
    "python_files_changed",
    "test_files_changed",
    "dependency_changes",
    "known_test_count",
    "previous_build_failed",
    "previous_3_build_failures",
    "historical_avg_duration",
    "historical_failure_rate",
]

# Post-execution information or labels. Must never reach the model.
FORBIDDEN_COLUMNS = [
    "build_duration", "pipeline_status", "failure_type", "injected_scenario", "failed_step",
    "finish_time", "start_time", "status", "scenario", "failed_test_count", "completion_time",
]

# Dataset columns in order (see docs/DATA_COLLECTION.md)
DATASET_COLUMNS = [
    "execution_id", "experiment_id", "timestamp", "commit_sha",
    *FEATURE_COLUMNS,
    "build_duration", "pipeline_status", "failure_type", "injected_scenario", "failed_step",
    "data_source",
]

# Build substitution name for each feature (Cloud Build user substitutions start with "_")
FEATURE_SUBSTITUTIONS = {c: "_" + c.upper() for c in FEATURE_COLUMNS}
FEATURE_SUBSTITUTIONS.update({
    "previous_build_failed": "_PREV_FAILED",
    "previous_3_build_failures": "_PREV3_FAILURES",
    "historical_avg_duration": "_HIST_AVG_DURATION",
    "historical_failure_rate": "_HIST_FAILURE_RATE",
    "python_files_changed": "_PY_FILES_CHANGED",
})


def env_name(feature: str) -> str:
    """Environment variable used to hand a feature to a Cloud Build step."""
    return "PG_" + FEATURE_SUBSTITUTIONS[feature].lstrip("_")


def assert_no_leakage(columns) -> None:
    """Raise if any forbidden (post-execution/label) column is about to be used as a feature."""
    bad = sorted(set(columns) & set(FORBIDDEN_COLUMNS))
    if bad:
        raise ValueError(f"Feature leakage: post-execution columns used as features: {bad}")
    unknown = sorted(set(columns) - set(FEATURE_COLUMNS))
    if unknown:
        raise ValueError(f"Unknown feature columns (not in FEATURE_COLUMNS): {unknown}")


def risk_category(probability: float, low: float = 0.40, high: float = 0.70) -> str:
    """LOW: p < low; MEDIUM: low <= p <= high; HIGH: p > high."""
    if probability is None or probability != probability:
        raise ValueError("probability must be a number")
    if probability < low:
        return "LOW"
    if probability > high:
        return "HIGH"
    return "MEDIUM"


def rule_based_probability(f: dict) -> float:
    """Transparent heuristic baseline (NOT learned from data; weights are a documented prior)."""
    def val(k):
        v = f.get(k)
        return 0.0 if v is None or v != v else float(v)

    score = 0.15
    if val("previous_build_failed") >= 1:
        score += 0.30
    if val("previous_3_build_failures") >= 2:
        score += 0.20
    if val("dependency_changes") > 0:
        score += 0.20
    if val("lines_added") + val("lines_deleted") > 200:
        score += 0.10
    if val("test_files_changed") == 0 and val("python_files_changed") > 0:
        score += 0.05
    return min(score, 0.95)
