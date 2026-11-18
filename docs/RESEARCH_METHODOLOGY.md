# Research methodology

**Question.** Can historical pipeline metadata and source-code change characteristics predict CI/CD pipeline
failures before execution?

**Compared strategies** (same chronological hold-out set, `ml/evaluate.py`):
1. Conventional CI/CD without prediction -> always predicts "success" (`no_prediction`).
2. Rule-based -> `pg.features.rule_based_probability`, a transparent hand-set heuristic, not learned from data.
3. Logistic Regression (balanced class weights, median imputation + missing indicators, standardisation).
4. Random Forest (200 trees, balanced subsample weights).

**Provenance.** A row exists only if a record fetched from the Cloud Build API passes `pg/provenance.py`: terminal
SUCCESS/FAILURE, matching IDs, project ID, timestamps, consistent parsed fields. Everything else is excluded and
listed with reasons in `storage/datasets/exclusions.json` (TIMEOUT/CANCELLED/INTERNAL_ERROR are infrastructure events,
not pipeline outcomes; builds stopped by the experimental risk gate are excluded because the model would be labelling itself).

**Controlled failure injection.** Scenarios A-F (`ci/scenarios.sh`) make the real steps fail (unresolvable requirement,
failing test, syntax error, empty config variable, import error). `failure_type` is derived from real step results:
`injected:<scenario>` only if the expected step failed, else `natural`. The scenario is stored for analysis and is
never a feature and is never passed to prediction steps (tested).

**Features** (pre-execution only): files/lines changed, Python/test files changed, dependency-file line changes,
known test count at the parent commit, previous build failed, failures in last 3, historical mean duration,
historical failure rate. **Leakage prevention:** `assert_no_leakage` on every training/prediction path; history for
each row is recomputed in `pg/dataset.py` using only builds that *finished before that build was created*;
a chronological split replaces random splitting.

**Metrics.** Accuracy, precision, recall, F1, ROC-AUC (when both classes are present), FPR, FNR, confusion matrix,
class distribution, at a 0.5 threshold with failure as the positive class. Because accuracy is misleading under
imbalance, read recall/FPR/AUC alongside it. Minimum-sample thresholds (`ml/preprocess.py`) flag results as
"not statistically meaningful" instead of reporting them as reliable.

**Class imbalance.** The default plan is 50% injected failures by design, which is *not* a natural failure rate.
Use `--weights` to change it; report results at more than one ratio.

**Generalisation.** See `LIMITATIONS.md`. In particular, with scenarios assigned independently of change features,
no model *should* beat chance on injected failures; a result near chance is a valid, honest outcome.

**Needed before any production-readiness claim:** real (non-injected) pipelines across several repositories and
teams; natural failure rates; prospective (online) evaluation in advisory mode; calibration analysis;
cost-benefit analysis of false positives; repeated runs with confidence intervals; comparison with flaky-test detectors.
No external references or published results are cited or invented here.
