# Sourced by the steps that execute a scenario. This is the single place where faults are injected.
REQ_FILE="target_app/requirements.txt"
TEST_PATHS="target_app/tests"
BUILD_FAULT=0
APP_CONFIG="${APP_CONFIG:-}"
case "${SCENARIO:-success}" in
  success) ;;
  unit_test_failure)    TEST_PATHS="target_app/tests target_app/faults/failing_tests" ;;
  build_failure)        BUILD_FAULT=1 ;;
  dependency_failure)   REQ_FILE="target_app/faults/requirements_unresolvable.txt" ;;
  config_failure)       APP_CONFIG="" ;;
  import_error_failure) TEST_PATHS="target_app/tests target_app/faults/import_error_tests" ;;
  *) echo "Unknown SCENARIO=${SCENARIO}" >&2; exit 64 ;;
esac
export REQ_FILE TEST_PATHS BUILD_FAULT APP_CONFIG
