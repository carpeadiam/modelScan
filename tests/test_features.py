from pipelineguard.features import FEATURES

def test_feature_list_excludes_post_build_fields():
    assert 'actual_build_outcome' not in FEATURES
    assert 'actual_duration' not in FEATURES
    assert 'experiment_scenario' not in FEATURES

def test_extract_features_uses_git_commit_before_build(tmp_path):
    import subprocess
    from pipelineguard.features import extract_features
    def git(*args):
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init')
    git('config', 'user.email', 'pipelineguard-test@example.invalid')
    git('config', 'user.name', 'PipelineGuard Test')
    (tmp_path/'app.py').write_text('print("ok")\n')
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests'/'test_app.py').write_text('def test_ok(): assert True\n')
    git('add', '.')
    git('commit', '-m', 'initial test fixture')
    commit, branch, features = extract_features(str(tmp_path), previous_records=[])
    assert len(commit)==40
    assert features['changed_files'] >= 1
    assert features['python_files_changed'] >= 1
    assert features['test_files_changed'] >= 1
    assert 'actual_build_outcome' not in features
