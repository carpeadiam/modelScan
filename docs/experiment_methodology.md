# Experiment methodology

## Research question

Can pre-build repository change characteristics and prior completed pipeline history help estimate the probability that a subsequent Cloudflare Preview build fails?

## Unit of observation

One unique Cloudflare build UUID associated with one commit SHA. The runner refuses to record the same build UUID twice and selects unused commits from the configured experiment branch. It will stop when no unused commits remain rather than repeatedly rebuilding one tree to inflate sample count.

## Outcome classes

- Success: Cloudflare terminal success.
- Failure: Cloudflare terminal failure.
- Excluded from binary training: cancelled, timed out, incomplete, API/collection errors.

Controlled failure scenarios must be introduced by a real source commit on a dedicated branch. The scenario name is retained as experiment metadata and never included in features. Balance targets are not forced or fabricated.

## Feature timing and leakage controls

Features are computed before the trigger request. Historical aggregates are built from previously collected terminal executions only. Current build logs, duration, outcome, status, completion time, and failure injection metadata are forbidden predictors.

## Sampling

Use a serial run to respect the one-concurrent-build plan limit. Start with five. Use distinct commits and document changes. A commit with no code changes may still add no useful feature diversity and should not be treated as a distinct experimental treatment without justification.

## Model evaluation

Logistic Regression is the baseline; Random Forest is the primary model. The script sorts observations chronologically and partitions distinct commits 70/15/15. It reports metrics only when train/test partitions have adequate records and both classes. For a research-grade study, expand this to grouped temporal validation and report confidence intervals after sufficient data is available.
