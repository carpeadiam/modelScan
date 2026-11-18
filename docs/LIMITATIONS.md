# Limitations

1. **Controlled failures are not natural failures.** Injected faults reflect which scenario the experimenter chose, not
   code-change risk. Because scenarios are assigned independently of the change features, a feature-based model has little
   to learn; expect near-chance performance on injected failures. This is a limitation of the design, not a bug to "fix"
   by correlating scenarios with features (that would leak the design into the data).
2. **Generated workload commits.** Change inputs are seeded and synthetic in *origin* (working code), though their metrics and
   all outcomes are real. A real repository's commit history would be more externally valid.
3. **One small Python project, one cloud, one runner configuration.** No generalisation claim to production pipelines.
4. **Failure rate is set by `--weights`.** Default 50% is an experimental convenience.
5. **Small samples.** 300 runs split chronologically leaves ~90 test rows; confidence intervals are wide. Thresholds in
   `ml/preprocess.py` are pragmatic, not formal power calculations.
6. **Temporal dependence.** Consecutive runs share a growing codebase; history features are autocorrelated.
7. **Parallel mode** slightly changes what "history available at submission" means (see DATA_COLLECTION).
8. **Infrastructure noise.** TIMEOUT/INTERNAL_ERROR/CANCELLED are excluded; transient network failures during `pip install`
   can show up as `natural` failures.
9. **Untested against live GCP in this delivery** (see README "Verification status"), including Monitoring/Logging queries.
