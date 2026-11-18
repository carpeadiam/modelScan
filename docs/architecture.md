# Architecture

The Python runner is the explicit orchestrator. Cloudflare Workers Builds does not provide a pre-build ML prediction hook in this design. The runner computes features, requests inference, records the prediction, then calls the Preview trigger endpoint.

```mermaid
sequenceDiagram
 participant Git as Git repository
 participant Runner as Python runner
 participant Model as Trained model
 participant CF as Cloudflare Builds API
 participant Worker as PipelineGuard Worker
 participant D1 as D1
 participant R2 as R2
 Git->>Runner: commit and Git diff/history
 Runner->>Runner: extract pre-build features
 Runner->>Model: score (if artifact exists)
 Model-->>Runner: probability or explicit untrained state
 Runner->>Worker: persist prediction (before build)
 Worker->>D1: predictions row
 Runner->>CF: POST Preview trigger build (branch + commit_hash)
 CF-->>Runner: build_uuid
 loop until terminal status or timeout
  Runner->>CF: list builds
  CF-->>Runner: status and outcome
 end
 Runner->>CF: fetch logs
 Runner->>Worker: authenticated ingestion
 Worker->>R2: raw response and logs, unique object key
 Worker->>D1: structured record with unique build UUID
```

## Boundaries

- Cloudflare API token: user-scoped, used by Python runner only.
- Build token UUID: separate deployment credential configured on the Cloudflare trigger.
- Worker ingestion key: separate shared secret; never reuse the Cloudflare API token.
- D1: queryable metadata and labels.
- R2: raw build response/log payload and trained model JSON.
- Dashboard: read-only data presentation; experiment execution is controlled from Codespaces CLI.
