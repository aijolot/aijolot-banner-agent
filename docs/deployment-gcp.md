# Deployment — Google Cloud Run + GitHub Actions (CI/CD)

The app ships as a **single container** (FastAPI backend + static React/Babel
frontend) running on **Cloud Run**, built and deployed by **GitHub Actions**
authenticating with **Workload Identity Federation** (no long-lived keys).

```
GitHub push to main
  └─ .github/workflows/deploy.yml
       ├─ auth to GCP via WIF (keyless OIDC)
       ├─ docker build (Dockerfile)  →  Artifact Registry
       └─ deploy-cloudrun            →  Cloud Run service "banner-agent"
              runtime config  ←  Secret Manager (mounted as /secrets/app.env)
```

## Components in this repo

| File | Purpose |
|------|---------|
| `Dockerfile` | python:3.11-slim + Chromium (Playwright). Preserves `/app/backend` + `/app/frontend` layout so `banner_render._frontend_dir()` resolves. |
| `backend/docker-entrypoint.sh` | Loads `/secrets/app.env` into the env, then runs uvicorn on `$PORT`. |
| `backend/app/main.py` | Mounts `frontend/` as same-origin StaticFiles (after all API routers). |
| `frontend/index.html` | Sets `window.AIJOLOT_API_BASE` to the same origin in prod. |
| `.github/workflows/deploy.yml` | CI/CD: build → push → deploy. |
| `scripts/gcp-bootstrap.sh` | One-time idempotent GCP setup (project, APIs, registry, SAs, WIF, secret). |

## One-time setup

### 1. Bootstrap GCP

Edit defaults at the top of `scripts/gcp-bootstrap.sh` if needed, then run.
Pass `BILLING_ACCOUNT` to auto-link billing (required for a brand-new project):

```bash
BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX \
RUNTIME_ENV_FILE=.env \
./scripts/gcp-bootstrap.sh
```

This creates the project `aijolot-banner-agent`, enables APIs, an Artifact
Registry repo, a deploy SA, a least-privilege runtime SA, the WIF pool/provider
scoped to `aijolot/aijolot-banner-agent`, and a Secret Manager secret seeded
from your local `.env`. It prints the GitHub variables to set.

### 2. Set GitHub repo variables

The script prints ready-to-paste `gh variable set ...` commands. They define:

`GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_REGION`, `GCP_ARTIFACT_REPO`,
`CLOUD_RUN_SERVICE`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`, `GCP_RUNTIME_SA`,
`RUNTIME_ENV_SECRET`.

> No GitHub **secrets** are required — runtime config lives in Secret Manager.

### 3. Deploy

Push to `main` (or run the workflow manually via the Actions tab →
"Deploy to Cloud Run" → Run workflow). The final step prints the service URL.

## Updating runtime config

Edit your local `.env`, then add a new secret version and redeploy
(the next deploy picks up `:latest`):

```bash
gcloud secrets versions add banner-agent-runtime-env --data-file=.env
gcloud run services update banner-agent --region us-central1 \
  --update-secrets=/secrets/app.env=banner-agent-runtime-env:latest
```

`APP_ENV=production` is baked into the image; `.env` overrides it at runtime if
present. Never commit `.env` — it is gitignored and excluded from the build via
`.dockerignore`.

## Local container test (optional)

```bash
docker build -t banner-agent:local .
docker run --rm -p 8080:8080 \
  -v "$PWD/.env:/secrets/app.env:ro" \
  banner-agent:local
# open http://localhost:8080  (frontend)  and  /docs (API)
```

## Notes & cost

- **Scale to zero** (`--min-instances=0`): no cost when idle; first request
  after idle pays a cold start (Chromium image is ~1–1.5 GB, so cold starts are
  a few seconds). Raise `--min-instances=1` for a warm demo.
- The service is deployed `--allow-unauthenticated` (public). Put it behind IAP
  or remove that flag if access should be restricted.
- Chromium runs with `--no-sandbox` (see `banner_render.py`), which is required
  inside the Cloud Run sandbox.
