from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    cf_api_token: str = os.getenv('CF_API_TOKEN', '')
    cf_account_id: str = os.getenv('CF_ACCOUNT_ID', '')
    cf_worker_tag: str = os.getenv('CF_WORKER_TAG', '')
    cf_preview_trigger_uuid: str = os.getenv('CF_PREVIEW_TRIGGER_UUID', '')
    build_branch: str = os.getenv('CF_BUILD_BRANCH', 'pipelineguard-experiment')
    api_url: str = os.getenv('PIPELINEGUARD_API_URL', '').rstrip('/')
    api_key: str = os.getenv('PIPELINEGUARD_API_KEY', '')
    timeout: int = int(os.getenv('BUILD_TIMEOUT_SECONDS', '1200'))
    poll_interval: int = int(os.getenv('POLL_INTERVAL_SECONDS', '15'))
    max_builds: int = int(os.getenv('MAX_EXPERIMENT_BUILDS', '300'))
    scenario: str = os.getenv('EXPERIMENT_SCENARIO', 'normal')

    def validate_cloudflare(self):
        missing = [k for k, v in {
            'CF_API_TOKEN': self.cf_api_token,
            'CF_ACCOUNT_ID': self.cf_account_id,
            'CF_WORKER_TAG': self.cf_worker_tag,
            'CF_PREVIEW_TRIGGER_UUID': self.cf_preview_trigger_uuid,
        }.items() if not v]
        if missing:
            raise ValueError('Missing required Cloudflare settings: ' + ', '.join(missing))

    def validate_ingest(self):
        if not self.api_url or not self.api_key:
            raise ValueError('Set PIPELINEGUARD_API_URL and PIPELINEGUARD_API_KEY to persist executions in D1/R2.')

settings = Settings()
