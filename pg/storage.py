"""Storage abstraction: local directory (development) or Google Cloud Storage (GCP mode).

The local directory starts EMPTY and is only ever filled by real collected records.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List

from .config import Settings, get_settings


def _check_key(key: str) -> str:
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError(f"Invalid storage key: {key!r}")
    return key


class Storage:
    def write_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...
    def read_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list_keys(self, prefix: str = "") -> List[str]: ...
    def delete(self, key: str) -> None: ...

    def write_json(self, key: str, obj) -> None:
        self.write_bytes(key, json.dumps(obj, indent=2, sort_keys=True, default=str).encode(), "application/json")

    def read_json(self, key: str):
        return json.loads(self.read_bytes(key).decode())

    def read_json_or_none(self, key: str):
        try:
            return self.read_json(key)
        except FileNotFoundError:
            return None


class LocalStorage(Storage):
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / _check_key(key)

    def write_bytes(self, key, data, content_type="application/octet-stream"):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)  # atomic

    def read_bytes(self, key):
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key):
        return self._path(key).is_file()

    def list_keys(self, prefix=""):
        out = []
        for p in self.root.rglob("*"):
            if p.is_file() and not p.name.startswith(".tmp-") and p.name != ".gitkeep":
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(prefix):
                    out.append(rel)
        return sorted(out)

    def delete(self, key):
        p = self._path(key)
        if p.is_file():
            p.unlink()


class GCSStorage(Storage):
    def __init__(self, bucket: str, project: str | None = None):
        from google.cloud import storage  # lazy import: not needed for local development

        self._client = storage.Client(project=project or None)
        self.bucket_name = bucket
        self._bucket = self._client.bucket(bucket)

    def write_bytes(self, key, data, content_type="application/octet-stream"):
        self._bucket.blob(_check_key(key)).upload_from_string(data, content_type=content_type)

    def read_bytes(self, key):
        from google.api_core.exceptions import NotFound

        try:
            return self._bucket.blob(_check_key(key)).download_as_bytes()
        except NotFound as exc:
            raise FileNotFoundError(key) from exc

    def exists(self, key):
        return self._bucket.blob(_check_key(key)).exists()

    def list_keys(self, prefix=""):
        return sorted(b.name for b in self._client.list_blobs(self.bucket_name, prefix=prefix)
                      if not b.name.endswith("/"))

    def delete(self, key):
        blob = self._bucket.blob(_check_key(key))
        if blob.exists():
            blob.delete()


def get_storage(settings: Settings | None = None) -> Storage:
    s = settings or get_settings()
    if s.use_gcp:
        if not s.bucket:
            raise RuntimeError("PG_USE_GCP=true but PG_BUCKET is not set.")
        return GCSStorage(s.bucket, s.project_id)
    return LocalStorage(s.local_storage_dir)
