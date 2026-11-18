set -uo pipefail
echo "== Stage 4: ML failure prediction (advisory) =="
mkdir -p /workspace/pg_out
OUT=/workspace/pg_out/prediction_report.json
if [ "${PG_ENABLE_PREDICTION:-true}" != "true" ]; then
  echo '{"status":"skipped","reason":"prediction disabled"}' > "$OUT"; exit 0
fi
if [ -f /workspace/model/metadata.json ]; then
  if pip install --quiet --no-cache-dir --target /workspace/.mldeps -r requirements-ml.txt \
     && PYTHONPATH=/workspace/.mldeps:/workspace python -m ml.predict \
          --model-dir /workspace/model --features-file /workspace/pg_out/pre_build_features.json --out "$OUT"; then
    cat "$OUT"
  else
    echo '{"status":"error","reason":"predictor failed; advisory only, build continues"}' > "$OUT"
  fi
else
  echo '{"status":"skipped","reason":"no trained model available"}' > "$OUT"
fi
exit 0   # advisory mode: the predictor can never fail the pipeline
