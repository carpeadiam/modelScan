# Deployment guide

1. Create a Cloudflare Worker and authorize the Cloudflare GitHub App for this repository in the dashboard.
2. Configure a Preview trigger for a non-production branch, with build command `npm ci && npm run build` and a non-production preview deploy command supported by your Worker configuration.
3. Create D1 (`pipelineguard-db`) and R2 (`pipelineguard-raw`).
4. Replace the D1 database ID placeholder in `worker/wrangler.jsonc`.
5. Apply migrations: `cd worker && npx wrangler d1 migrations apply pipelineguard-db --remote`.
6. Set the Worker secret: `npx wrangler secret put PIPELINEGUARD_API_KEY`.
7. Build dashboard from repo root: `npm install && npm --prefix dashboard install && npm --prefix worker install && npm test && npm run build`.
8. Deploy: `cd worker && npm install && npx wrangler deploy`.
9. Set Codespaces secrets and run one build.

The Cloudflare GitHub App authorization is a manual security step. A Worker tag is immutable and differs from the Worker name. The Builds API uses a user-scoped API token, distinct from the build token UUID used by the build system.
