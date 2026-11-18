"""Scenario B (controlled fault): a test that genuinely fails when pytest runs inside Cloud Build."""


def test_intentional_failure():
    assert 1 + 1 == 3, "intentional controlled failure (PipelineGuard fault injection)"
