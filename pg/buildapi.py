"""Cloud Build API: response parsing (pure functions, unit-tested) and a thin client wrapper."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .features import FEATURE_COLUMNS, FEATURE_SUBSTITUTIONS

TERMINAL = {"SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}
LABELLED = {"SUCCESS", "FAILURE"}   # statuses that can serve as a pipeline_status label
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def parse_ts(value) -> Optional[datetime]:
    """RFC3339 (nanosecond precision allowed) -> aware datetime. None if absent."""
    if not value:
        return None
    m = _TS.match(value)
    if not m:
        raise ValueError(f"Unparseable timestamp: {value!r}")
    base, frac, tz = m.groups()
    frac = (frac or ".0")[:7].ljust(7, "0")
    tz = "+00:00" if tz == "Z" else tz
    return datetime.fromisoformat(f"{base}{frac}{tz}").astimezone(timezone.utc)


def _seconds(a, b):
    return None if a is None or b is None else (b - a).total_seconds()


def parse_build(build: dict) -> dict:
    """Normalise a Cloud Build `Build` JSON object. Missing values stay None (never invented)."""
    create, start, finish = (parse_ts(build.get(k)) for k in ("createTime", "startTime", "finishTime"))
    steps = []
    failed_step = None
    for st in build.get("steps", []) or []:
        timing = st.get("timing") or {}
        s0, s1 = parse_ts(timing.get("startTime")), parse_ts(timing.get("endTime"))
        steps.append({"id": st.get("id"), "name": st.get("name"), "status": st.get("status"),
                      "duration_seconds": _seconds(s0, s1)})
        if st.get("status") == "FAILURE" and failed_step is None:
            failed_step = st.get("id")
    name = build.get("name", "") or ""
    m = re.search(r"locations/([^/]+)/builds/", name)
    subs = build.get("substitutions") or {}
    repo_src = ((build.get("sourceProvenance") or {}).get("resolvedRepoSource") or {})
    commit = repo_src.get("commitSha") or subs.get("COMMIT_SHA") or subs.get("_COMMIT_SHA") or None
    return {
        "execution_id": build.get("id"),
        "status": build.get("status"),
        "create_time": create.isoformat() if create else None,
        "start_time": start.isoformat() if start else None,
        "finish_time": finish.isoformat() if finish else None,
        "duration_seconds": _seconds(start, finish),
        "queue_seconds": _seconds(create, start),
        "region": m.group(1) if m else "global",
        "trigger_id": build.get("buildTriggerId") or None,
        "commit_sha": commit,
        "steps": steps,
        "failed_step": failed_step,
        "log_url": build.get("logUrl"),
        "logs_bucket": build.get("logsBucket"),
        "project_id": build.get("projectId"),
    }


def _num(value):
    if value in (None, ""):
        return None
    f = float(value)
    return int(f) if f.is_integer() and "." not in str(value) else f


def extract_meta(build: dict) -> dict:
    """Recover PipelineGuard metadata that the runner stored in the build's own substitutions."""
    subs = build.get("substitutions") or {}
    feats = {col: _num(subs.get(FEATURE_SUBSTITUTIONS[col])) for col in FEATURE_COLUMNS}
    return {
        "experiment_id": subs.get("_EXPERIMENT_ID") or None,
        "run_index": _num(subs.get("_RUN_INDEX")),
        "injected_scenario": subs.get("_SCENARIO") or None,
        "commit_sha": subs.get("_COMMIT_SHA") or None,
        "submitted_features": feats,
    }


def is_terminal(build: dict) -> bool:
    return build.get("status") in TERMINAL


def is_retriable(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as gx
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, (gx.ResourceExhausted, gx.ServiceUnavailable, gx.DeadlineExceeded,
                            gx.InternalServerError, gx.TooManyRequests, gx.Aborted))


class CloudBuildApi:
    """Wrapper over google-cloud-build (official client). Requires authenticated GCP access."""

    def __init__(self, project_id: str, region: str = "global"):
        from google.cloud.devtools import cloudbuild_v1

        self._mod = cloudbuild_v1
        self._client = cloudbuild_v1.CloudBuildClient()
        self.project_id, self.region = project_id, region

    def _to_dict(self, build) -> dict:
        return json.loads(self._mod.Build.to_json(build, use_integers_for_enums=False))

    def submit(self, config: dict, substitutions: Dict[str, str], tags: List[str], bucket: str, source_object: str) -> str:
        cfg = json.loads(json.dumps(config))
        cfg["source"] = {"storageSource": {"bucket": bucket, "object": source_object}}
        cfg["substitutions"] = {k: str(v) for k, v in substitutions.items()}
        cfg["tags"] = tags
        build = self._mod.Build.from_json(json.dumps(cfg))
        request = {"project_id": self.project_id, "build": build}
        if self.region != "global":
            request["parent"] = f"projects/{self.project_id}/locations/{self.region}"
        op = self._client.create_build(request=request)
        return op.metadata.build.id

    def get(self, build_id: str) -> dict:
        if self.region == "global":
            req = {"project_id": self.project_id, "id": build_id}
        else:
            req = {"name": f"projects/{self.project_id}/locations/{self.region}/builds/{build_id}"}
        return self._to_dict(self._client.get_build(request=req))

    def find_by_tag(self, tag: str) -> List[dict]:
        req = {"project_id": self.project_id, "filter": f'tags="{tag}"', "page_size": 100}
        if self.region != "global":
            req["parent"] = f"projects/{self.project_id}/locations/{self.region}"
        return [self._to_dict(b) for b in self._client.list_builds(request=req)]

    def preflight(self) -> None:
        """Raises with the underlying error if credentials / API / permissions are missing."""
        req = {"project_id": self.project_id, "page_size": 1}
        if self.region != "global":
            req["parent"] = f"projects/{self.project_id}/locations/{self.region}"
        next(iter(self._client.list_builds(request=req)), None)
