set -euo pipefail
echo "== Stage 5b: configuration check =="
source ci/scenarios.sh
PYTHONPATH=/workspace/.deps:/workspace python -m target_app.src.config_check
