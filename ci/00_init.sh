set -euo pipefail
echo "== PipelineGuard stage 1: environment initialisation =="
python --version
mkdir -p /workspace/pg_out
source ci/scenarios.sh   # validates the scenario name only
echo "BUILD_ID=${BUILD_ID:-unknown}  PROJECT_ID=${PROJECT_ID:-unknown}"
