"""Controlled failure-injection scenarios.

The scenario is passed ONLY to the Cloud Build steps that execute it (see cloudbuild.yaml and
ci/scenarios.sh). It is recorded in the raw execution record for analysis and is NEVER a model feature.
"""
from __future__ import annotations

import random
from typing import Dict, List

SCENARIOS: Dict[str, dict] = {
    "success": {"label": "A: Successful execution", "expected_failing_step": None},
    "unit_test_failure": {"label": "B: Unit test failure", "expected_failing_step": "unit-tests"},
    "build_failure": {"label": "C: Build command failure", "expected_failing_step": "build"},
    "dependency_failure": {"label": "D: Dependency installation failure", "expected_failing_step": "install-dependencies"},
    "config_failure": {"label": "E: Missing configuration / env var", "expected_failing_step": "config-check"},
    "import_error_failure": {"label": "F: Test collection (import) error", "expected_failing_step": "unit-tests"},
}

DEFAULT_WEIGHTS = {
    "success": 0.50, "unit_test_failure": 0.10, "build_failure": 0.10,
    "dependency_failure": 0.10, "config_failure": 0.10, "import_error_failure": 0.10,
}


def parse_weights(text: str | None) -> Dict[str, float]:
    if not text:
        return dict(DEFAULT_WEIGHTS)
    weights = {}
    for part in text.split(","):
        name, _, value = part.partition("=")
        name = name.strip()
        if name not in SCENARIOS:
            raise ValueError(f"Unknown scenario {name!r}. Valid: {sorted(SCENARIOS)}")
        weights[name] = float(value)
    if sum(weights.values()) <= 0:
        raise ValueError("Scenario weights must sum to > 0")
    return weights


def plan_scenarios(count: int, weights: Dict[str, float], seed: str) -> List[str]:
    """Deterministic allocation (largest remainder) followed by a seeded shuffle."""
    total = sum(weights.values())
    raw = {k: count * v / total for k, v in weights.items()}
    alloc = {k: int(v) for k, v in raw.items()}
    leftover = count - sum(alloc.values())
    for k in sorted(raw, key=lambda k: raw[k] - alloc[k], reverse=True)[:leftover]:
        alloc[k] += 1
    plan = [k for k, n in alloc.items() for _ in range(n)]
    random.Random(f"{seed}:scenario-plan").shuffle(plan)
    return plan


def classify_failure(status: str, scenario: str | None, failed_step: str | None) -> str:
    """Failure source from REAL step results: none | natural | injected:<scenario> | blocked_by_prediction_gate."""
    if status != "FAILURE":
        return "none"
    if failed_step == "risk-gate":
        return "blocked_by_prediction_gate"
    expected = SCENARIOS.get(scenario or "", {}).get("expected_failing_step")
    if scenario and scenario != "success" and expected and failed_step == expected:
        return f"injected:{scenario}"
    return "natural"
