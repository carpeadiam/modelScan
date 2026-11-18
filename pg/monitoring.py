"""Real Google Cloud telemetry (Cloud Monitoring + Cloud Logging). Degrades to an explicit 'unavailable'."""
from __future__ import annotations

import os
import time

from .config import Settings


def snapshot(settings: Settings, hours: int = 24) -> dict:
    out = {"available": False, "reason": None, "deployment": {
        "service": os.environ.get("K_SERVICE"), "revision": os.environ.get("K_REVISION"),
        "configuration": os.environ.get("K_CONFIGURATION")}}
    if not (settings.use_gcp and settings.project_id):
        out["reason"] = "GCP mode is disabled (PG_USE_GCP=false); no Google Cloud telemetry to show."
        return out
    try:
        from google.cloud import monitoring_v3

        client = monitoring_v3.MetricServiceClient()
        now = int(time.time())
        interval = monitoring_v3.TimeInterval({"end_time": {"seconds": now}, "start_time": {"seconds": now - hours * 3600}})
        A = monitoring_v3.Aggregation.Aligner

        def series(metric, aligner, extra=""):
            agg = monitoring_v3.Aggregation({"alignment_period": {"seconds": 3600}, "per_series_aligner": aligner})
            flt = (f'metric.type="{metric}" AND resource.labels.service_name="{settings.service_name}"{extra}')
            pts = []
            for ts in client.list_time_series(request={
                    "name": f"projects/{settings.project_id}", "filter": flt, "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL, "aggregation": agg}):
                for p in ts.points:
                    v = p.value.double_value or p.value.int64_value
                    pts.append((p.interval.end_time.timestamp(), v))
            return sorted(pts)

        out["request_count_hourly"] = series("run.googleapis.com/request_count", A.ALIGN_SUM)
        out["latency_p95_ms_hourly"] = series("run.googleapis.com/request_latencies", A.ALIGN_PERCENTILE_95)
        out["memory_utilization_p95_hourly"] = series("run.googleapis.com/container/memory/utilizations", A.ALIGN_PERCENTILE_95)
        out["available"] = True
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"Cloud Monitoring query failed: {type(exc).__name__}: {exc}"
    try:
        from google.cloud import logging as gcl

        lc = gcl.Client(project=settings.project_id)
        flt = (f'(resource.type="cloud_run_revision" AND resource.labels.service_name="{settings.service_name}" '
               f'AND severity>=ERROR) OR (resource.type="build" AND severity>=ERROR)')
        out["recent_errors"] = [{"time": str(e.timestamp), "severity": e.severity,
                                 "text": str(e.payload)[:300]} for e in
                                lc.list_entries(filter_=flt, order_by=gcl.DESCENDING, max_results=15)]
        out["available"] = True
    except Exception as exc:  # noqa: BLE001
        out["logging_reason"] = f"Cloud Logging query failed: {type(exc).__name__}: {exc}"
    return out
