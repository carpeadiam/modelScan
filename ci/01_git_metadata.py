"""Stage 2: record the Git change metrics (computed from the real commit diff at submission time)."""
import json, os, sys
sys.path.insert(0, os.getcwd())
from pg.features import FEATURE_COLUMNS, env_name  # noqa: E402

def conv(v):
    if v in (None, ""):
        return None
    f = float(v)
    return int(f) if f.is_integer() else f

features = {c: conv(os.environ.get(env_name(c))) for c in FEATURE_COLUMNS}
out = {"commit_sha": os.environ.get("PG_COMMIT_SHA"), "features": features}
os.makedirs("/workspace/pg_out", exist_ok=True)
json.dump(out, open("/workspace/pg_out/pre_build_features.json", "w"), indent=2)
print("Stage 2/3 pre-build features:", json.dumps(out, indent=2))
