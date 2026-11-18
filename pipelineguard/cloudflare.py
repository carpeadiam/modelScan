import time
import requests

BASE = 'https://api.cloudflare.com/client/v4'

class CloudflareError(RuntimeError):
    pass

class CloudflareBuilds:
    def __init__(self, account_id, token, worker_tag, trigger_uuid, timeout=1200, poll_interval=15):
        self.account = account_id
        self.worker_tag = worker_tag
        self.trigger_uuid = trigger_uuid
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})

    def _request(self, method, path, **kwargs):
        url = f'{BASE}/accounts/{self.account}/{path.lstrip("/")}'
        for attempt in range(5):
            response = self.session.request(method, url, timeout=30, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 4:
                    response.raise_for_status()
                time.sleep(min(2 ** attempt, 20))
                continue
            response.raise_for_status()
            data = response.json()
            if data.get('success') is False:
                raise CloudflareError(str(data.get('errors', data)))
            return data.get('result')
        raise CloudflareError('Cloudflare request retry limit exceeded')

    def verify_trigger(self):
        triggers = self._request('GET', f'builds/workers/{self.worker_tag}/triggers')
        matches = [t for t in (triggers or []) if t.get('trigger_uuid') == self.trigger_uuid]
        if not matches:
            raise CloudflareError('Configured Preview trigger UUID was not found for this Worker tag.')
        return matches[0]

    def find_existing_build(self, branch, commit_hash):
        result = self.list_builds()
        records = result if isinstance(result, list) else (result or {}).get('builds', [])
        for item in records:
            metadata = item.get('build_trigger_metadata') or {}
            item_branch = item.get('branch') or metadata.get('branch')
            item_commit = item.get('commit_hash') or metadata.get('commit_hash')
            if item_branch == branch and item_commit == commit_hash and item.get('build_uuid'):
                return item
        return None

    def trigger(self, branch, commit_hash):
        result = self._request('POST', f'builds/triggers/{self.trigger_uuid}/builds',
                               json={'branch': branch, 'commit_hash': commit_hash})
        if not isinstance(result, dict) or not result.get('build_uuid'):
            raise CloudflareError(f'Unexpected trigger response; build_uuid missing: {result}')
        return result

    def list_builds(self, page=1, per_page=50):
        return self._request('GET', f'builds/workers/{self.worker_tag}/builds',
                             params={'page': page, 'per_page': per_page})

    def get_logs(self, build_uuid):
        return self._request('GET', f'builds/builds/{build_uuid}/logs')

    def wait_for_build(self, build_uuid):
        deadline = time.monotonic() + self.timeout
        latest = None
        while time.monotonic() < deadline:
            # Cloudflare's list endpoint is authoritative; locate the UUID in recent builds.
            result = self.list_builds()
            records = result if isinstance(result, list) else (result or {}).get('builds', [])
            latest = next((b for b in records if b.get('build_uuid') == build_uuid), None)
            if latest:
                status = str(latest.get('status', '')).lower()
                outcome = str(latest.get('build_outcome', '')).lower()
                if status in {'success', 'failed', 'failure', 'cancelled', 'canceled', 'complete', 'completed'} or outcome in {'success', 'failure', 'failed'}:
                    logs = self.get_logs(build_uuid)
                    return latest, logs
            time.sleep(self.poll_interval)
        raise TimeoutError(f'Build {build_uuid} did not reach a terminal state within {self.timeout}s')

    @staticmethod
    def classify(build):
        status = str(build.get('status', '')).lower()
        outcome = str(build.get('build_outcome', '')).lower()
        if status in {'cancelled', 'canceled'}:
            return 'cancelled'
        if outcome in {'success', 'succeeded'} or status == 'success':
            return 'success'
        if outcome in {'failure', 'failed'} or status in {'failed', 'failure'}:
            return 'failure'
        return 'incomplete'
