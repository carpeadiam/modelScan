"""Scenario F (controlled fault): test collection fails with a real ImportError."""
import pipelineguard_module_that_does_not_exist  # noqa: F401


def test_never_reached():
    pass
