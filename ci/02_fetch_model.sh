set -uo pipefail
echo "== Stage 3: fetch latest trained model (if any) =="
mkdir -p /workspace/model
if gcloud storage cp "gs://${MODEL_BUCKET}/models/*" /workspace/model/ ; then
  ls -l /workspace/model
else
  echo "No trained model found in gs://${MODEL_BUCKET}/models/ - prediction will be skipped."
fi
exit 0
