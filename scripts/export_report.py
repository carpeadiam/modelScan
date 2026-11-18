#!/usr/bin/env python3
"""Write reports/experiment_report.md from REAL dataset + evaluation only."""
import _bootstrap  # noqa: F401
from datetime import datetime, timezone

from ml.preprocess import load_dataset
from pg.config import ROOT, get_settings
from pg.storage import get_storage


def main():
    st = get_storage(get_settings())
    df, m = load_dataset(st), st.read_json_or_none("reports/model_metrics.json")
    L = ["# PipelineGuard experiment report", f"_Generated {datetime.now(timezone.utc).isoformat()}_", ""]
    if df is None or df.empty:
        L.append("No verified real executions available. Nothing to report.")
    else:
        L += [f"- Verified executions: **{len(df)}**",
              f"- Outcomes: {df['pipeline_status'].value_counts().to_dict()}",
              f"- Failure types: {df['failure_type'].value_counts().to_dict()}",
              f"- Period: {df['timestamp'].min()} -> {df['timestamp'].max()}", ""]
    if m:
        L += ["## Model evaluation (chronological hold-out)", ""]
        if m.get("caution"):
            L += [f"> **{m['caution']}**", ""]
        L += ["| strategy | acc | prec | recall | f1 | auc | FPR | FNR |", "|---|---|---|---|---|---|---|---|"]
        f = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
        for n, x in {**m["baselines"], **m["models"]}.items():
            L.append(f"| {n} | " + " | ".join(f(x[k]) for k in ("accuracy", "precision", "recall", "f1", "roc_auc",
                                                                  "false_positive_rate", "false_negative_rate")) + " |")
    out = ROOT / "reports" / "experiment_report.md"
    out.write_text("\n".join(L) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
