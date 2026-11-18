from pathlib import Path

def test_runner_requires_large_confirmation_and_unique_commit_guard():
    source=(Path(__file__).parents[1]/'scripts'/'run_experiment.py').read_text()
    assert '--confirm-large' in source
    assert 'No unused commits remain' in source
