"""Data-provenance verification for raw execution records."""
from __future__ import annotations

from typing import List, Tuple

from .buildapi import LABELLED, TERMINAL, parse_build

DATA_SOURCE = "cloud_build_api"
VERIFY_METHOD = "cloudbuild_api.get_build"
SCHEMA_VERSION = 1


def verify_record(rec: dict) -> Tuple[bool, List[str]]:
    """A record is trainable only if it was fetched from the Cloud Build API and is internally consistent."""
    reasons: List[str] = []
    if not isinstance(rec, dict):
        return False, ["not_an_object"]
    exec_id = rec.get("execution_id")
    build = rec.get("build")
    ver = rec.get("verification") or {}
    if not exec_id:
        reasons.append("missing_execution_id")
    if not isinstance(build, dict) or not build:
        reasons.append("missing_raw_cloud_build_payload")
        return False, reasons
    if ver.get("verified") is not True or ver.get("method") != VERIFY_METHOD:
        reasons.append("not_verified_via_cloud_build_api")
    if rec.get("data_source") != DATA_SOURCE:
        reasons.append("data_source_not_cloud_build_api")
    if build.get("id") != exec_id:
        reasons.append("execution_id_mismatch_with_api_payload")
    if not build.get("projectId"):
        reasons.append("missing_project_id_in_api_payload")
    if not build.get("createTime"):
        reasons.append("missing_create_time")
    status = build.get("status")
    if status not in TERMINAL:
        reasons.append(f"incomplete_execution:{status}")
    elif status not in LABELLED:
        reasons.append(f"non_labelled_terminal_status:{status}")
    if status in LABELLED and not build.get("finishTime"):
        reasons.append("missing_finish_time")
    if not reasons:
        try:
            parsed = parse_build(build)
            stored = rec.get("parsed") or {}
            if stored.get("status") != parsed["status"] or stored.get("create_time") != parsed["create_time"]:
                reasons.append("parsed_fields_inconsistent_with_raw_payload")
        except Exception as exc:  # malformed timestamps etc.
            reasons.append(f"unparseable_payload:{exc}")
    return (not reasons), reasons
