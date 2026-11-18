#!/usr/bin/env python3
"""Run real Cloudflare Preview builds serially; resume from verified records."""
import argparse, json, os, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelineguard.config import settings
from pipelineguard.features import extract_features
from pipelineguard.cloudflare import CloudflareBuilds
from pipelineguard.store import PipelineGuardAPI

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'dataset' / 'experiment_progress.json'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--count', type=int, default=1)
    p.add_argument('--confirm-large', action='store_true')
    p.add_argument('--fresh', action='store_true')
    args = p.parse_args()
    if args.count < 1 or args.count > settings.max_builds:
        p.error(f'--count must be between 1 and configured MAX_EXPERIMENT_BUILDS={settings.max_builds}')
    if args.count > 5 and not args.confirm_large:
        p.error('Large campaigns require --confirm-large. Start with --count 5.')
    settings.validate_cloudflare(); settings.validate_ingest()
    api = PipelineGuardAPI(settings.api_url, settings.api_key)
    cf = CloudflareBuilds(settings.cf_account_id, settings.cf_api_token, settings.cf_worker_tag,
                          settings.cf_preview_trigger_uuid, settings.timeout, settings.poll_interval)
    trigger = cf.verify_trigger()
    if args.fresh and PROGRESS.exists(): PROGRESS.unlink()
    progress = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {'campaign_id': str(uuid.uuid4()), 'requested': args.count, 'completed_uuids': [], 'started_at': datetime.now(timezone.utc).isoformat()}
    progress['requested'] = max(progress.get('requested', 0), args.count)
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    prior = api.builds()
    prior_uuids = {r.get('cloudflare_build_uuid') for r in prior}
    used_commits = {r.get('commit_sha') for r in prior if r.get('commit_sha')}
    # Each observation uses a distinct commit to avoid presenting repeated builds of one tree as diverse data.
    import subprocess
    commits = subprocess.check_output(['git', '-C', str(ROOT), 'rev-list', '--reverse', settings.build_branch], text=True).splitlines()
    candidates = [sha for sha in commits if sha not in used_commits]
    completed = len(progress['completed_uuids'])
    print(f"Preview trigger verified: {trigger.get('trigger_name', settings.cf_preview_trigger_uuid)}")
    print(f'Resuming campaign {progress["campaign_id"]}: {completed}/{args.count} requested builds already completed.')
    try:
        while completed < args.count:
            if not candidates:
                raise RuntimeError('No unused commits remain on CF_BUILD_BRANCH. Push distinct source commits to that branch, then resume. The runner will not duplicate a commit to inflate the dataset.')
            commit_ref = candidates.pop(0)
            commit, branch, features = extract_features(ROOT, prior, commit_ref=commit_ref, branch_ref=settings.build_branch)
            execution_id = str(uuid.uuid4())
            prediction = {'probability': None, 'label': None, 'model_status': 'Model not trained: insufficient real execution history.'}
            model_path = ROOT / 'artifacts' / 'model.json'
            if model_path.exists():
                try:
                    prediction = api.predict(features)
                except Exception as exc:
                    print(f'Prediction unavailable (build will still run): {exc}')
            # Persist the pre-build prediction before triggering Cloudflare.
            api.record_prediction({'execution_id': execution_id, 'commit_sha': commit, 'branch': settings.build_branch, 'timestamp': datetime.now(timezone.utc).isoformat(), 'features': features, 'probability': prediction.get('probability'), 'label': prediction.get('label'), 'model_status': prediction.get('model_status', 'unknown')})
            # Branch must be a configured remote branch visible to Cloudflare.
            build_branch = settings.build_branch
            print(f'[{completed + 1}/{args.count}] Triggering real Preview build for {build_branch}@{commit[:10]}')
            triggered_at = datetime.now(timezone.utc).isoformat()
            existing = cf.find_existing_build(build_branch, commit)
            if existing:
                print('  Existing automatic build found for this exact branch/commit; reusing it to avoid a duplicate trigger.')
                trigger_result = existing
            else:
                trigger_result = cf.trigger(build_branch, commit)
            build_uuid = trigger_result['build_uuid']
            if build_uuid in prior_uuids:
                raise RuntimeError(f'Cloudflare returned previously recorded build UUID {build_uuid}; refusing duplicate record.')
            build, logs = cf.wait_for_build(build_uuid)
            outcome = cf.classify(build)
            created = build.get('created_on') or build.get('created_at') or triggered_at
            finished = build.get('completed_on') or build.get('finished_on')
            duration = build.get('duration')
            if duration is None and build.get('started_on') and finished:
                from datetime import datetime as dt
                duration = max(0, (dt.fromisoformat(finished.replace('Z', '+00:00')) - dt.fromisoformat(build['started_on'].replace('Z', '+00:00'))).total_seconds())
            record = {
                'execution_id': execution_id, 'cloudflare_build_uuid': build_uuid,
                'commit_sha': commit, 'branch': build.get('branch') or build_branch,
                'timestamp': created, 'features': features,
                'prediction_probability': prediction.get('probability'), 'predicted_label': prediction.get('label'),
                'actual_build_status': build.get('status'), 'actual_build_outcome': outcome,
                'actual_duration': duration, 'experiment_scenario': settings.scenario,
                'collection_status': 'verified' if outcome in ('success', 'failure') else outcome,
                'raw_build': build, 'raw_logs': logs,
            }
            if outcome not in ('success', 'failure'):
                record['collection_status'] = outcome
            api.ingest(record)
            progress['completed_uuids'].append(build_uuid)
            progress['last_execution_at'] = datetime.now(timezone.utc).isoformat()
            PROGRESS.write_text(json.dumps(progress, indent=2))
            prior.append({**record, 'actual_build_outcome': outcome})
            prior_uuids.add(build_uuid)
            used_commits.add(commit)
            completed += 1
            print(f'  {build_uuid}: {outcome} ({duration if duration is not None else "duration unavailable"} seconds)')
    except KeyboardInterrupt:
        print('\nStopped safely. Progress is saved; rerun the same command to resume.')
        return 130
    print(f'Campaign progress: {completed}/{args.count}.')
    return 0

if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr); raise
