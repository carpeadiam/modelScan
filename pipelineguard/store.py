import requests

class PipelineGuardAPI:
    def __init__(self, base_url, api_key):
        self.base = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})

    def _get(self, path, **params):
        r = self.session.get(self.base + path, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def _post(self, path, payload):
        r = self.session.post(self.base + path, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def builds(self, limit=500):
        data = self._get('/api/builds', limit=limit)
        return data.get('builds', [])

    def ingest(self, record):
        return self._post('/api/ingest', record)

    def record_prediction(self, prediction):
        return self._post('/api/predictions', prediction)

    def predict(self, features):
        return self._post('/api/predict', {'features': features})
