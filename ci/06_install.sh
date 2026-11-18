set -euo pipefail
echo "== Stage 5a: dependency installation =="
source ci/scenarios.sh
pip install --no-cache-dir --target /workspace/.deps -r "$REQ_FILE"
