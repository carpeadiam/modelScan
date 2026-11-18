from datetime import datetime, timezone
from pathlib import Path
import subprocess

FEATURES = [
    'changed_files', 'additions', 'deletions', 'python_files_changed',
    'test_files_changed', 'dependency_changed', 'config_files_changed',
    'previous_build_failed', 'previous_3_failure_count',
    'historical_avg_duration', 'commit_age', 'branch_type'
]

DEPENDENCY_FILES = {'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'requirements.txt', 'pyproject.toml', 'poetry.lock'}
CONFIG_NAMES = {'wrangler.json', 'wrangler.jsonc', 'vite.config.ts', 'tsconfig.json', 'Dockerfile'}

def _git(repo: str, *args: str) -> str:
    return subprocess.check_output(['git', '-C', repo, *args], text=True, stderr=subprocess.DEVNULL).strip()

def extract_features(repo='.', previous_records=None, commit_ref='HEAD', branch_ref=None):
    """Compute only pre-build features for a selected commit and earlier completed records."""
    previous_records = previous_records or []
    commit = _git(repo, 'rev-parse', commit_ref)
    branch = branch_ref or _git(repo, 'branch', '--show-current')
    committed = int(_git(repo, 'show', '-s', '--format=%ct', commit_ref))
    changed = []
    additions = deletions = 0
    try:
        parent = _git(repo, 'rev-parse', f'{commit_ref}^')
        raw = _git(repo, 'diff', '--numstat', parent, commit_ref)
        for line in raw.splitlines():
            parts = line.split('\t', 2)
            if len(parts) != 3:
                continue
            a, d, filename = parts
            changed.append(filename)
            additions += int(a) if a.isdigit() else 0
            deletions += int(d) if d.isdigit() else 0
    except (subprocess.CalledProcessError, ValueError):
        # First commit / shallow checkout: compare against empty tree.
        raw = _git(repo, 'show', '--pretty=format:', '--name-only', commit_ref)
        changed = [x for x in raw.splitlines() if x]
    completed = [r for r in previous_records if r.get('actual_build_outcome') in ('success', 'failure')]
    completed.sort(key=lambda r: r.get('timestamp', ''))
    last3 = completed[-3:]
    durations = [float(r['actual_duration']) for r in completed if r.get('actual_duration') is not None]
    now = datetime.now(timezone.utc).timestamp()
    features = {
        'changed_files': len(changed),
        'additions': additions,
        'deletions': deletions,
        'python_files_changed': sum(p.endswith('.py') for p in changed),
        'test_files_changed': sum(('test' in Path(p).name.lower()) or p.startswith('tests/') for p in changed),
        'dependency_changed': int(any(Path(p).name in DEPENDENCY_FILES for p in changed)),
        'config_files_changed': int(any(Path(p).name in CONFIG_NAMES for p in changed)),
        'previous_build_failed': int(bool(completed and completed[-1].get('actual_build_outcome') == 'failure')),
        'previous_3_failure_count': sum(r.get('actual_build_outcome') == 'failure' for r in last3),
        'historical_avg_duration': sum(durations) / len(durations) if durations else 0.0,
        'commit_age': max(0.0, now - committed),
        'branch_type': 0 if branch in ('main', 'master') else 1,
    }
    return commit, branch, features
