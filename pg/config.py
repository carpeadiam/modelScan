"""Environment-driven configuration. No credentials are ever read from or written to the repo."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    use_gcp: bool = False
    project_id: str = ""
    region: str = "us-central1"          # Cloud Run / bucket region
    bucket: str = ""
    build_region: str = "global"          # Cloud Build region ("global" = default)
    service_name: str = "pipelineguard"
    local_storage_dir: Path = ROOT / "storage"
    max_runs: int = 300
    max_concurrency: int = 4
    risk_low: float = 0.40
    risk_high: float = 0.70

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            use_gcp=_bool("PG_USE_GCP", False),
            project_id=os.environ.get("GCP_PROJECT_ID", ""),
            region=os.environ.get("GCP_REGION", "us-central1"),
            bucket=os.environ.get("PG_BUCKET", ""),
            build_region=os.environ.get("PG_BUILD_REGION", "global"),
            service_name=os.environ.get("PG_SERVICE_NAME", "pipelineguard"),
            local_storage_dir=Path(os.environ.get("PG_LOCAL_STORAGE", str(ROOT / "storage"))),
            max_runs=int(os.environ.get("PG_MAX_RUNS", "300")),
            max_concurrency=int(os.environ.get("PG_MAX_CONCURRENCY", "4")),
            risk_low=float(os.environ.get("PG_RISK_LOW", "0.40")),
            risk_high=float(os.environ.get("PG_RISK_HIGH", "0.70")),
        )


def get_settings() -> Settings:
    return Settings.from_env()
