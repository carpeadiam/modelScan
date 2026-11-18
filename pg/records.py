"""Per-execution raw records (one JSON object per build -> no concurrent CSV writes)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from .buildapi import extract_meta, parse_build
from .provenance import DATA_SOURCE, SCHEMA_VERSION, VERIFY_METHOD
from .storage import Storage

RAW_PREFIX = "raw/builds/"


def record_key(execution_id: str) -> str:
    return f"{RAW_PREFIX}{execution_id}.json"


def make_record(build: dict, project_id: str) -> dict:
    """Wrap a Cloud Build API response. Call ONLY with the payload returned by the API."""
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_id": build.get("id"),
        "data_source": DATA_SOURCE,
        "verification": {"verified": True, "method": VERIFY_METHOD, "project_id": project_id,
                         "verified_at": datetime.now(timezone.utc).isoformat()},
        "build": build,
        "parsed": parse_build(build),
        "pipelineguard": extract_meta(build),
    }


def save_record(storage: Storage, record: dict) -> str:
    key = record_key(record["execution_id"])
    storage.write_json(key, record)  # same id -> same key -> naturally de-duplicated
    return key


def load_records(storage: Storage) -> List[dict]:
    out = []
    for key in storage.list_keys(RAW_PREFIX):
        if key.endswith(".json"):
            out.append(storage.read_json(key))
    return out
