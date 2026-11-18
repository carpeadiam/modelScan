set -uo pipefail
gcloud storage cp /workspace/pg_out/prediction_report.json "gs://${BUCKET}/reports/predictions/${BUILD_ID}.json" || echo "WARN: could not upload prediction report"
exit 0
