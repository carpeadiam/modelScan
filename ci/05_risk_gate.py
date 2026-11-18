"""Advisory by default: HIGH risk -> warning. Experimental blocking mode (off by default) fails the step."""
import json, os, sys
rep = json.load(open("/workspace/pg_out/prediction_report.json"))
blocking = os.environ.get("BLOCKING_MODE", "false").lower() == "true"
if rep.get("risk_category") == "HIGH":
    print(f"WARNING: PipelineGuard predicts HIGH failure risk (p={rep.get('failure_probability'):.2f}, "
          f"model={rep.get('model_used')}, validated={rep.get('model_validated')}).")
    if blocking:
        print("BLOCKING MODE (experimental) is enabled: stopping the build.")
        sys.exit(1)
    print("Advisory mode: build continues.")
else:
    print("Prediction report:", {k: rep.get(k) for k in ("status", "risk_category", "failure_probability", "reason")})
