set -euo pipefail
echo "== Stage 6: unit tests =="
source ci/scenarios.sh
PYTHONPATH=/workspace/.deps:/workspace python -m pytest -q -p no:cacheprovider $TEST_PATHS
