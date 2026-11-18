set -uo pipefail
echo "== Stage 7: pipeline result reporting =="
python3 - <<'PY'
import json, os
s = {"build_id": os.environ.get("BUILD_ID"), "status_reached_report_step": True,
     "note": "Only runs when all earlier steps succeeded. Authoritative result = Cloud Build API."}
json.dump(s, open("/workspace/pg_out/pipeline_summary.json", "w"), indent=2); print(s)
PY
gcloud storage cp /workspace/pg_out/pipeline_summary.json "gs://${BUCKET}/reports/pipeline_summaries/${BUILD_ID}.json" || echo "WARN: summary upload failed"
exit 0
