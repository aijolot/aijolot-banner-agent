#!/usr/bin/env bash
#
# One-time (idempotent) GCP bootstrap for the Aijolot Banner Agent Cloud Run
# deployment with GitHub Actions + Workload Identity Federation.
#
# What it creates:
#   - A dedicated GCP project (optional; skipped if it already exists)
#   - Enabled APIs: run, artifactregistry, secretmanager, iamcredentials, sts, cloudbuild
#   - An Artifact Registry Docker repo
#   - A deploy service account (github-deployer) with deploy-time roles
#   - A least-privilege runtime service account (banner-agent-runtime)
#   - A Workload Identity Pool + OIDC provider for GitHub, scoped to this repo
#   - A Secret Manager secret holding the runtime .env (from a local file)
#
# It prints the exact GitHub repo VARIABLES to set at the end.
#
# Usage:
#   chmod +x scripts/gcp-bootstrap.sh
#   ./scripts/gcp-bootstrap.sh
#
# Override any default via env vars, e.g.:
#   PROJECT_ID=aijolot-banner-agent BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX \
#   RUNTIME_ENV_FILE=.env ./scripts/gcp-bootstrap.sh
set -euo pipefail

# ---- Config (override via environment) --------------------------------------
PROJECT_ID="${PROJECT_ID:-aijolot-banner-agent}"
PROJECT_NAME="${PROJECT_NAME:-Aijolot Banner Agent}"
REGION="${REGION:-us-central1}"
ARTIFACT_REPO="${ARTIFACT_REPO:-containers}"
SERVICE="${SERVICE:-banner-agent}"
GITHUB_REPO="${GITHUB_REPO:-aijolot/aijolot-banner-agent}"   # owner/repo
DEPLOY_SA_NAME="${DEPLOY_SA_NAME:-github-deployer}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-banner-agent-runtime}"
POOL_ID="${POOL_ID:-github-pool}"
PROVIDER_ID="${PROVIDER_ID:-github-provider}"
RUNTIME_SECRET="${RUNTIME_SECRET:-banner-agent-runtime-env}"
RUNTIME_ENV_FILE="${RUNTIME_ENV_FILE:-.env}"
BILLING_ACCOUNT="${BILLING_ACCOUNT:-}"   # XXXXXX-XXXXXX-XXXXXX; required to create a new project

DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA_EMAIL="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }

command -v gcloud >/dev/null || { echo "gcloud not found"; exit 1; }

# ---- 1. Project -------------------------------------------------------------
say "Project: $PROJECT_ID"
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Project already exists"
else
  gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME"
  ok "Project created"
fi
gcloud config set project "$PROJECT_ID" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
ok "Project number: $PROJECT_NUMBER"

# ---- 2. Billing -------------------------------------------------------------
say "Billing"
if [ "${SKIP_BILLING:-}" = "1" ]; then
  ok "SKIP_BILLING=1 — assuming billing is already linked"
elif ! gcloud beta --help >/dev/null 2>&1; then
  echo "  ! gcloud 'beta' component not installed — skipping billing check."
  echo "    Set SKIP_BILLING=1 to silence this, or install with: gcloud components install beta"
elif gcloud beta billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null | grep -qi true; then
  ok "Billing already linked"
else
  if [ -z "$BILLING_ACCOUNT" ]; then
    echo "  Available billing accounts:"
    gcloud beta billing accounts list || true
    echo "  Re-run with BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX to link billing automatically."
    echo "  (APIs that require billing will fail until this is linked.)"
  else
    gcloud beta billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
    ok "Billing linked"
  fi
fi

# ---- 3. APIs ----------------------------------------------------------------
say "Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  cloudbuild.googleapis.com
ok "APIs enabled"

# ---- 4. Artifact Registry ---------------------------------------------------
say "Artifact Registry repo: $ARTIFACT_REPO ($REGION)"
if gcloud artifacts repositories describe "$ARTIFACT_REPO" --location="$REGION" >/dev/null 2>&1; then
  ok "Repo already exists"
else
  gcloud artifacts repositories create "$ARTIFACT_REPO" \
    --repository-format=docker --location="$REGION" \
    --description="Aijolot Banner Agent container images"
  ok "Repo created"
fi

# ---- 5. Service accounts ----------------------------------------------------
say "Service accounts"
if ! gcloud iam service-accounts describe "$DEPLOY_SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$DEPLOY_SA_NAME" --display-name="GitHub Actions deployer"
fi
ok "Deploy SA: $DEPLOY_SA_EMAIL"
if ! gcloud iam service-accounts describe "$RUNTIME_SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$RUNTIME_SA_NAME" --display-name="Banner Agent Cloud Run runtime"
fi
ok "Runtime SA: $RUNTIME_SA_EMAIL"

# ---- 6. IAM roles -----------------------------------------------------------
say "Granting IAM roles"
# Deployer: deploy to Cloud Run, push images, and act as the runtime SA.
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" --role="$role" --condition=None >/dev/null
done
# Allow the deployer to actAs the runtime SA specifically (deploy with --service-account).
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA_EMAIL" \
  --member="serviceAccount:${DEPLOY_SA_EMAIL}" --role="roles/iam.serviceAccountUser" >/dev/null
ok "Deployer roles granted"

# ---- 7. Runtime secret ------------------------------------------------------
say "Runtime secret: $RUNTIME_SECRET"
if ! gcloud secrets describe "$RUNTIME_SECRET" >/dev/null 2>&1; then
  gcloud secrets create "$RUNTIME_SECRET" --replication-policy=automatic
  ok "Secret created"
else
  ok "Secret already exists"
fi
if [ -f "$RUNTIME_ENV_FILE" ]; then
  gcloud secrets versions add "$RUNTIME_SECRET" --data-file="$RUNTIME_ENV_FILE"
  ok "Added new secret version from $RUNTIME_ENV_FILE"
else
  echo "  ! $RUNTIME_ENV_FILE not found — add a version later with:"
  echo "    gcloud secrets versions add $RUNTIME_SECRET --data-file=.env"
fi
# Runtime SA can read the secret.
gcloud secrets add-iam-policy-binding "$RUNTIME_SECRET" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" --role="roles/secretmanager.secretAccessor" >/dev/null
ok "Runtime SA can access the secret"

# ---- 8. Workload Identity Federation ----------------------------------------
say "Workload Identity Federation (GitHub OIDC)"
if ! gcloud iam workload-identity-pools describe "$POOL_ID" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location=global --display-name="GitHub Actions pool"
fi
ok "Pool: $POOL_ID"

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
      --location=global --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --location=global --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'"
fi
ok "Provider: $PROVIDER_ID (scoped to ${GITHUB_REPO})"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

# Let GitHub Actions from this repo impersonate the deploy SA.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}" >/dev/null
ok "Repo ${GITHUB_REPO} can impersonate ${DEPLOY_SA_EMAIL}"

# ---- 9. Output --------------------------------------------------------------
say "Done. Set these GitHub repo VARIABLES (Settings → Secrets and variables → Actions → Variables):"
cat <<EOF

  GCP_PROJECT_ID      = ${PROJECT_ID}
  GCP_PROJECT_NUMBER  = ${PROJECT_NUMBER}
  GCP_REGION          = ${REGION}
  GCP_ARTIFACT_REPO   = ${ARTIFACT_REPO}
  CLOUD_RUN_SERVICE   = ${SERVICE}
  GCP_WIF_PROVIDER    = ${WIF_PROVIDER}
  GCP_DEPLOY_SA       = ${DEPLOY_SA_EMAIL}
  GCP_RUNTIME_SA      = ${RUNTIME_SA_EMAIL}
  RUNTIME_ENV_SECRET  = ${RUNTIME_SECRET}

Set them quickly with the gh CLI:

  gh variable set GCP_PROJECT_ID     --body "${PROJECT_ID}"
  gh variable set GCP_PROJECT_NUMBER --body "${PROJECT_NUMBER}"
  gh variable set GCP_REGION         --body "${REGION}"
  gh variable set GCP_ARTIFACT_REPO  --body "${ARTIFACT_REPO}"
  gh variable set CLOUD_RUN_SERVICE  --body "${SERVICE}"
  gh variable set GCP_WIF_PROVIDER   --body "${WIF_PROVIDER}"
  gh variable set GCP_DEPLOY_SA      --body "${DEPLOY_SA_EMAIL}"
  gh variable set GCP_RUNTIME_SA     --body "${RUNTIME_SA_EMAIL}"
  gh variable set RUNTIME_ENV_SECRET --body "${RUNTIME_SECRET}"

Then push to main (or run the workflow manually) to deploy.
EOF
