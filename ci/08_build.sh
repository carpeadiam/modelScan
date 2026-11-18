set -euo pipefail
echo "== Stage 5c: build (byte-compile sources) =="
source ci/scenarios.sh
rm -rf build_out && mkdir -p build_out
cp -r target_app/src build_out/src
if [ "$BUILD_FAULT" = "1" ]; then cp target_app/faults/bad_syntax.txt build_out/src/bad_syntax.py; fi
python -m compileall -q build_out/src
echo "Build OK: $(find build_out/src -name '*.py' | wc -l) python modules compiled"
