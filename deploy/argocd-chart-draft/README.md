# DRAFT — ArgoCD Helm chart for ahq-mcp-server

**This is a draft only. Nothing here has been pushed to `kubernetes-argocd-apps` or any other repo.**
It exists so the DevOps team can review/adjust before it's placed at
`release/charts/ahq-mcp-server/` in `AutomationHQ-Canada/kubernetes-argocd-apps`.

**Not yet validated with `helm template`/`helm lint`** — `helm` isn't installed in this environment.
The templates are hand-adapted from `release/charts/ahq-background-v2-services`'s real, working
chart (field substitutions only, same structure), but DevOps should run `helm template .` /
`helm lint .` against this before merging it anywhere.

## Why this is needed

`kubernetes-argocd-apps` runs an ArgoCD `ApplicationSet` (`release/root-apps/ApplicationSet/ahq-dev.yaml`)
that auto-discovers any directory under `release/charts/*` and deploys it via
`values-dev.yaml` — no other registration step is required *beyond* the chart existing there.
Today there is no chart for `ahq-mcp-server` (nor for the colleague's `automationhq-mcp-server`),
so even a correctly-firing CI/CD pipeline has nothing to deploy to.

This draft mirrors `release/charts/ahq-background-v2-services`'s shape exactly (same
Deployment/Service/ConfigMap structure already used for every other `ahq-*` backend service),
adapted for this being a stateless Python service with no database and no per-tenant secrets
stored server-side (hosted mode reads each caller's AHQ credentials from request headers, not
from container config — see `src/config/credentials.py`).

## What's DELIBERATELY different from ahq-background-v2-services' chart

- No `secrets:` block / `templates/secret.yaml` — this service holds no tenant secrets.
- No Kafka/MongoDB/S3/Azure config in the ConfigMap — this service only needs `AHQ_BASE_URL`.
- `readinessProbe` path is `/healthz` (this service's actual health route), not `/actuator/health`
  (a Spring Boot convention that doesn't apply here).
- `containerPort: 8000`, matching this repo's `Dockerfile`/`http_server.py` default port.

## Open questions for DevOps to confirm before this goes live

1. **Does an ECR repository named `ahq-mcp-server` already exist** in account `501429054313` /
   `us-east-2`? If not, it needs to be created before the CI pipeline's first push.
2. **`serviceAccountName: ahq-dev-service-account`** — copied from `ahq-background-v2-services`'
   dev values on the assumption every dev-namespace service shares one service account. Confirm
   this is correct, or provide the right one.
3. **Resource requests/limits** — I used the same numbers already in this repo's root-level
   `deployment.yml` (300Mi/200m request, 800Mi/1000m limit) as a starting guess. This server does
   no CPU-heavy work itself (just proxies HTTP calls), so these may be oversized — DevOps/whoever
   owns cluster capacity planning should sanity-check.
4. **Whether an Ingress is needed at all** — probably not: `ahq-gateway-services` already routes
   `/ahq-mcp-server/**` to `http://ahq-mcp-server:8000/` via plain in-cluster service DNS (see the
   gateway route already committed in `ahq-gateway-services`), the same way every other backend
   service is reached. No `templates/ingress.yaml` is included here on that assumption — flag if
   wrong.
5. **HPA/VPA** — left disabled (`enabled: false`) for v1, matching `ahq-background-v2-services`'
   dev defaults, since there's no load data yet to size autoscaling against.

## How this is meant to be used

1. Hand this directory to DevOps (or whoever has write access to `kubernetes-argocd-apps`) for review.
2. Once approved, its contents get copied to `release/charts/ahq-mcp-server/` in that repo (a
   separate PR there — this repo's CI/CD dispatch already targets that path via
   `.github/workflows/ci.yml`'s `update-image-tag-dev` event).
3. Only after that chart exists there will a merge to `ahq-mcp-server`'s `main` result in an actual
   running pod — until then, CI will build+push to ECR successfully but the GitOps auto-deploy step
   has nothing to update.
